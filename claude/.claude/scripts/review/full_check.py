#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] [--base <rev>] -- '<command>'

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `failed (exit N)` with the failing step's lines after it (each lint
error with its file:line, the FAIL and ERROR lines; the log's last lines when the log holds none),
`not run (check-command error: <line>)` when a step of the command stops on a path that does not exist and did not
exist at the diff base either (`--base`, HEAD by default; a path the diff removed or moved is a failure),
`not run (timeout)` when the command runs past the limit, or `not run (CI)` when the repo's CLAUDE.md holds the line
`Full suite: CI` (the command does not run then). `run` with no command returns `not run (no check found; ...)`.
A command past the limit is killed with its whole process group, so no test process outlives the check. A repo with
a `.python-version` file runs the command with the pyenv shims first on PATH. A failed check whose log says
`No module named X`, for an X that the repo declares as a dependency (requirements*.txt, pyproject.toml, setup.cfg
or Pipfile, by normalized name), prints `not run (environment gap: No module named 'X')`.
Exit 0, or 1 when the check failed.
"""

import argparse
import configparser
import os
import pathlib
import posixpath
import re
import shlex
import signal
import subprocess
import sys
import tomllib

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]

import script_utils

FULL_SUITE_IN_CI = "Full suite: CI"
LIST_MARKER = re.compile(r"^\s*[-*]\s+")
PASSED = "passed"
NOT_RUN_CI = "not run (CI)"
NOT_RUN_TIMEOUT = "not run (timeout)"
NOT_RUN_NO_CHECK = "not run (no check found; the coder's scoped tests stand)"
MISSING_MODULE = re.compile(r"No module named '?([A-Za-z_][\w.]*)'?")
REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# Under the Bash tool's 600 s ceiling, so a loop's shell call ends before the tool moves it to the background.
DEFAULT_TIMEOUT_SECONDS = 540
TAIL_LINES = 40
# A lint error: ruff's rule line, then its ` --> file:line:col` line.
LINT_RULE_LINE = re.compile(r"^[A-Z]+\d+ ")
LINT_LOCATION_LINE = re.compile(r"^\s*--> \S+:\d+:\d+")
TEST_FAILURE_LINE = re.compile(r"^(?:FAIL|ERROR|FAILED)\b:?\s")
# A step that stops on a path that does not exist. The command is wrong, not the code, when the path did not exist at
# the diff base either.
MISSING_PATH_LINES = (
    re.compile(r"^fatal: ambiguous argument '(?P<path>.*)': unknown revision or path not in the working tree"),
    re.compile(r"^\S*sh: (?:line \d+: )?(?:cd: )?(?P<path>\S+): No such file or directory"),
    re.compile(r"^\S*sh: \d+: cd: can't cd to (?P<path>\S+)"),
)


def full_suite_runs_in_ci(repo):
    """True when the repo's CLAUDE.md holds the line `Full suite: CI`, alone or as a list item."""
    claude_md = pathlib.Path(repo) / "CLAUDE.md"
    if not claude_md.is_file():
        return False

    lines = claude_md.read_text(errors="replace").splitlines()
    return any(LIST_MARKER.sub("", line).strip() == FULL_SUITE_IN_CI for line in lines)


def pinned_interpreter_env(repo, env):
    """`env` with the pyenv shims first on PATH when the repo pins a Python with `.python-version`."""
    check_env = dict(os.environ if env is None else env)
    if not (pathlib.Path(repo) / ".python-version").is_file():
        return check_env

    pyenv_root = pathlib.Path(check_env.get("PYENV_ROOT") or pathlib.Path.home() / ".pyenv")
    shims = pyenv_root / "shims"
    if not shims.is_dir():
        return check_env

    check_env["PATH"] = os.pathsep.join([str(shims), check_env.get("PATH", "")])
    return check_env


def distribution_name(requirement):
    """The normalized distribution name a requirement string starts with, or None."""
    found = REQUIREMENT_NAME.match(requirement.strip())
    if not found:
        return None
    return normalized_name(found.group(0))


def normalized_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements_txt_names(repo_path):
    names = set()
    for requirements in repo_path.glob("requirements*.txt"):
        for line in requirements.read_text(errors="replace").splitlines():
            if line.strip().startswith(("#", "-")):
                continue
            names.add(distribution_name(line))
    return names


def read_toml(path):
    if not path.is_file():
        return {}

    try:
        return tomllib.loads(path.read_text(errors="replace"))
    except tomllib.TOMLDecodeError:
        return {}


def pyproject_names(repo_path):
    pyproject = read_toml(repo_path / "pyproject.toml")
    project = pyproject.get("project", {})
    requirements = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        requirements += extra
    for group in pyproject.get("dependency-groups", {}).values():
        requirements += [entry for entry in group if isinstance(entry, str)]

    poetry = pyproject.get("tool", {}).get("poetry", {})
    poetry_tables = [poetry.get("dependencies", {}), poetry.get("dev-dependencies", {})]
    poetry_tables += [group.get("dependencies", {}) for group in poetry.get("group", {}).values()]
    for table in poetry_tables:
        requirements += list(table)
    return {distribution_name(requirement) for requirement in requirements}


def setup_cfg_names(repo_path):
    setup_cfg = repo_path / "setup.cfg"
    if not setup_cfg.is_file():
        return set()

    parser = configparser.ConfigParser()
    try:
        parser.read_string(setup_cfg.read_text(errors="replace"))
    except configparser.Error:
        return set()

    requirements = parser.get("options", "install_requires", fallback="").splitlines()
    if parser.has_section("options.extras_require"):
        for _, extra in parser.items("options.extras_require"):
            requirements += extra.splitlines()
    return {distribution_name(requirement) for requirement in requirements}


def pipfile_names(repo_path):
    pipfile = read_toml(repo_path / "Pipfile")
    packages = [*pipfile.get("packages", {}), *pipfile.get("dev-packages", {})]
    return {normalized_name(package) for package in packages}


def declared_distributions(repo):
    """The normalized distribution names the repo's dependency files declare."""
    repo_path = pathlib.Path(repo)
    names = requirements_txt_names(repo_path) | pyproject_names(repo_path)
    names |= setup_cfg_names(repo_path) | pipfile_names(repo_path)
    names.discard(None)
    return names


def environment_gap(repo, log_text):
    """The `No module named 'X'` line of a failed check whose X the repo declares as a dependency, or None."""
    declared = declared_distributions(repo)
    for found in MISSING_MODULE.finditer(log_text):
        module = found.group(1)
        top_level = module.split(".")[0]
        if normalized_name(top_level) in declared:
            return f"No module named '{module}'"
    return None


def failing_step_lines(log_lines):
    """The lint errors with their file:line and the FAIL and ERROR lines of a failed check's log, in log order."""
    picked = []
    for index, line in enumerate(log_lines):
        is_lint_error = (LINT_RULE_LINE.match(line) and index + 1 < len(log_lines)
                         and LINT_LOCATION_LINE.match(log_lines[index + 1]))
        if is_lint_error:
            picked += [line, log_lines[index + 1]]
        elif TEST_FAILURE_LINE.match(line):
            picked.append(line)
    return picked


def missing_path_match(line):
    return next((match for pattern in MISSING_PATH_LINES if (match := pattern.match(line))), None)


def existed_at_base(repo, base, path):
    """True when the base tree holds the path, as a file or a folder, from the repo root or from any folder below it
    (a CI step can run in a subfolder). A path outside the repo, or a base git cannot read, never existed there."""
    if posixpath.isabs(path):
        repo_root = str(pathlib.Path(repo).resolve())
        if not path.startswith(repo_root + "/"):
            return False
        path = path[len(repo_root) + 1:]
    wanted = posixpath.normpath(path).strip("/")

    base_listing = script_utils.git_output(repo, "ls-tree", "-r", "--name-only", base)
    if base_listing is None:
        return False

    for name in base_listing.splitlines():
        rooted = "/" + name + "/"
        if f"/{wanted}/" in rooted:
            return True
    return False


def run(repo, check_command, log, timeout, env=None, on_start=None, base="HEAD"):
    """Run the full check once. Returns (result, the lines that show it: the failing step's lines on a failure, else
    the log's last lines). `on_start`, when given, is called with the pid of the process group the check leads."""
    if full_suite_runs_in_ci(repo):
        return NOT_RUN_CI, ""
    if check_command is None:
        return NOT_RUN_NO_CHECK, ""

    env = pinned_interpreter_env(repo, env)
    with pathlib.Path(log).open("w") as handle:
        process = subprocess.Popen(check_command, shell=True, cwd=repo, stdout=handle, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        if on_start:
            on_start(process.pid)
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            exit_code = None

    log_text = pathlib.Path(log).read_text(errors="replace")
    log_lines = log_text.splitlines()
    tail = "\n".join(log_lines[-TAIL_LINES:])
    if exit_code is None:
        return NOT_RUN_TIMEOUT, tail
    if exit_code == 0:
        return PASSED, tail

    gap = environment_gap(repo, log_text)
    if gap:
        return f"not run (environment gap: {gap})", tail

    missing_path_line = next((line for line in log_lines[-TAIL_LINES:] if missing_path_match(line)), None)
    if missing_path_line:
        missing_path = missing_path_match(missing_path_line).group("path")
        if not existed_at_base(repo, base, missing_path):
            return f"not run (check-command error: {missing_path_line.strip()})", tail

    failing_lines = failing_step_lines(log_lines)
    return f"failed (exit {exit_code})", "\n".join(failing_lines) if failing_lines else tail


def is_failure(result):
    return result.startswith("failed")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--base", default="HEAD")
    if "--" not in argv:
        parser.error("no command after --")

    separator = argv.index("--")
    args = parser.parse_args(argv[:separator])

    command_words = argv[separator + 1:]
    check_command = shlex.join(command_words) if len(command_words) > 1 else "".join(command_words)
    if not check_command:
        parser.error("no command after --")

    result, tail = run(args.repo, check_command, args.log, args.timeout, base=args.base)
    print(f"full check: {result}")
    if is_failure(result):
        print(tail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
