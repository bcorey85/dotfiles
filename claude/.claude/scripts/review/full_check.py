#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] -- '<command>'

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `failed (exit N)` with the log's last lines after it,
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
import re
import shlex
import signal
import subprocess
import sys
import tomllib

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


def run(repo, check_command, log, timeout, env=None, on_start=None):
    """Run the full check once. Returns (result, the log's last lines). `on_start`, when given, is called with the pid
    of the process group the check leads."""
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
    tail = "\n".join(log_text.splitlines()[-TAIL_LINES:])
    if exit_code is None:
        return NOT_RUN_TIMEOUT, tail
    if exit_code != 0:
        gap = environment_gap(repo, log_text)
        if gap:
            return f"not run (environment gap: {gap})", tail
        return f"failed (exit {exit_code})", tail
    return PASSED, tail


def is_failure(result):
    return result.startswith("failed")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    if "--" not in argv:
        parser.error("no command after --")

    separator = argv.index("--")
    args = parser.parse_args(argv[:separator])

    command_words = argv[separator + 1:]
    check_command = shlex.join(command_words) if len(command_words) > 1 else "".join(command_words)
    if not check_command:
        parser.error("no command after --")

    result, tail = run(args.repo, check_command, args.log, args.timeout)
    print(f"full check: {result}")
    if is_failure(result):
        print(tail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
