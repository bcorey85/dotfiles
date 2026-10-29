#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] [--base <rev>] [--plan <path> --phase <id>] -- '<command>'

With --plan and --phase, the phase's `Expected red:` lines whose later phase is still open leave their `&&` steps out
of the command (lib/expected_red.py), and each left-out line prints as `expected red: <command> until Phase <id>`
after the result line. When they leave out the whole command, nothing runs and the result is
`not run (expected red until Phase <id>)`.

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `unverified (exit 0, no runner summary)` when the command exited 0 but
printed no test runner's own summary line, `failed (exit N)` with the failing step's lines after it (on a lint
error, each lint error with its file:line, the FAIL and ERROR lines, vitest's leading-space FAIL and \xd7 lines and the
`FAILED: <steps>` step-summary lines; else the failing tests and the log's last lines), `setup fault (exit N)` with
the same when the environment could not run the check (no program, a runner that cannot start, no package manifest,
no test found, a package-manager or engine version mismatch), `not run (check-command error: <line>)` when a step of
the command stops on a path that does not exist and did not exist at the diff base either (`--base`, HEAD by
default; a path the diff removed or moved is a failure), `not run (timeout)` when the command runs past the limit, or
`not run (CI)` when the repo's CLAUDE.md holds the line `Full suite: CI` (the command does not run
then, scoped or not), or `not run (scoped command: ...)` when the command runs tests or lint on named files or tests,
or with a changed-files flag, and its text does not equal the CLAUDE.md `Quality check:` command (it does not run
then). A `passed` or `unverified` result is followed by `summary: <the runner summary lines joined with " | ">` or
`summary: not found`. `run` with no command returns `not run (no check found; ...)`.
Tracked files the command rewrote and files it created are left in place and named (`changed by the check: <paths>`,
`created by the check: <paths>`). A file that held edits before the check and was rewritten is named on its own line
(`rewrote edited files: <paths>`). Exit 0 with a runner summary that counts failures is a failure.
A command past the limit is killed with its whole process group, so no test process outlives the check. A repo with
a `.python-version` file runs the command with the pyenv shims first on PATH. A failed check whose log says
`No module named X`, for an X that the repo declares as a dependency (requirements*.txt, pyproject.toml, setup.cfg
or Pipfile, by normalized name), prints `not run (environment gap: No module named 'X')`.
Exit 0, or 1 when the check failed or hit a setup fault; 2 for a usage error, such as a --log path that still holds
a template placeholder.
"""

import argparse
import collections
import configparser
import os
import pathlib
import posixpath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]

import check_scope
import expected_red
import script_utils
from check_output import (
    FAILING_TEST_LINE,
    failing_block_details,
    is_setup_fault,
    missing_path,
    normalized_log_line,
    tail_with_failing_tests,
)
from linked_installs import VENV_FOLDERS, holds_editable_install, import_path_enters_repo
from test_run_output import MAX_RUNNER_SUMMARIES, runner_summaries
from worktree_snapshot import CHANGE_KINDS, changes_since, take

FULL_SUITE_IN_CI = "Full suite: CI"
LIST_MARKER = re.compile(r"^\s*[-*]\s+")
# The CLAUDE.md line that names the repo's full check; group 1 is the command.
QUALITY_CHECK_LINE = re.compile(r"^\s*[-*]?\s*Quality check:\s*`([^`]+)`", re.I | re.M)
# A log name that still holds a template placeholder: `...`, or a `<branch>` never filled in.
UNFILLED_LOG_NAME = re.compile(r"\.\.\.|[<>]")
SUMMARY_SEPARATOR = " | "
PASSED = "passed"
# Exit 0 with no test runner's summary in the output: the command may have run no test, or the wrong ones.
UNVERIFIED = "unverified (exit 0, no runner summary)"
# Exit 0 whose runner summary still counts failures: a wrapper that swallowed the runner's exit code.
FAILED_EXIT_ZERO = "failed (exit 0, summary reports failures)"
SUMMARY_FAILURE = re.compile(
    r"\b[1-9]\d* (?:failed|failing|errors?)\b|FAILED \(|^[1-9]\d* fail$|^(?:#|\N{INFORMATION SOURCE}) fail [1-9]\d*$"
    r"|^FAIL\t", re.MULTILINE)
NOT_RUN_CI = "not run (CI)"
NOT_RUN_TIMEOUT = "not run (timeout)"
# The check could not run here: no program, a runner that cannot start, no package manifest, no test found, or a
# package-manager or engine version mismatch.
SETUP_FAULT = "setup fault"
NOT_RUN_NO_CHECK = "not run (no check found; the coder's scoped tests stand)"
NOT_RUN_SCOPED = "not run (scoped command: it names files or tests, so it is no full check)"
MISSING_MODULE = re.compile(r"No module named '?([A-Za-z_][\w.]*)'?")
REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# Under the Bash tool's 600 s ceiling, so a loop's shell call ends before the tool moves it to the background.
DEFAULT_TIMEOUT_SECONDS = 540
TAIL_LINES = 40
# A lint error: ruff's rule line, then its ` --> file:line:col` line.
LINT_RULE_LINE = re.compile(r"^[A-Z]+\d+ ")
LINT_LOCATION_LINE = re.compile(r"^\s*--> \S+:\d+:\d+")
# The line tests/run.sh prints for a failed step (`FAILED: lint duplicate-check`).
FAILED_STEPS_LINE = re.compile(r"^FAILED: ")
# Where the base worktree lives, under the repo's git common dir.
BASE_TREE_FOLDER = "full-check-base"
# The check fails the same way on HEAD without the diff. Not a failure: it starts with neither "failed" nor "not run".
# A check that stops early on the old failure (lint before test, a collection error, -x) never ran the diff's tests.
PRE_EXISTING = "pre-existing failure (the check fails the same way without this diff, so it did not verify this diff)"
# A substring that marks a log line as an error; it matches inside words too (`0 errors` counts).
ERROR_MARKER = re.compile(r"error|fail|exception|traceback|panic", re.IGNORECASE)
# The check run on HEAD without the diff: its result, failing lines, log lines and the detail lines under each failure.
BaseRun = collections.namedtuple("BaseRun", "result failing_lines log_lines failing_details")
# Untracked folders a check needs that a fresh worktree of HEAD lacks.
UNTRACKED_DEPENDENCY_FOLDERS = ("node_modules", *VENV_FOLDERS)


def full_suite_runs_in_ci(repo):
    """True when the repo's CLAUDE.md holds the line `Full suite: CI`, alone or as a list item."""
    claude_md = pathlib.Path(repo) / "CLAUDE.md"
    if not claude_md.is_file():
        return False

    lines = claude_md.read_text(errors="replace").splitlines()
    return any(LIST_MARKER.sub("", line).strip() == FULL_SUITE_IN_CI for line in lines)


def configured_check_command(repo):
    """The command of the repo's CLAUDE.md `Quality check:` line, or None when the file or the line is missing."""
    claude_md = pathlib.Path(repo) / "CLAUDE.md"
    if not claude_md.is_file():
        return None

    match = QUALITY_CHECK_LINE.search(claude_md.read_text(errors="replace"))
    if not match:
        return None

    return match.group(1)


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
    """The lint errors with their file:line, the FAIL and ERROR lines (vitest's leading-space FAIL and \xd7 lines too)
    and the `FAILED: <steps>` step-summary lines of a failed check's log, in log order."""
    picked = []
    for index, line in enumerate(log_lines):
        is_lint_error = (LINT_RULE_LINE.match(line) and index + 1 < len(log_lines)
                         and LINT_LOCATION_LINE.match(log_lines[index + 1]))
        if is_lint_error:
            picked += [line, log_lines[index + 1]]
        elif FAILING_TEST_LINE.match(line) or FAILED_STEPS_LINE.match(line):
            picked.append(line)
    return picked


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


def run_check_command(repo, check_command, log, timeout, env, on_start):
    """The exit code of the command run through the shell in the repo, output to the log; None when it ran past the
    limit and was killed with its process group."""
    with pathlib.Path(log).open("w") as handle:
        process = subprocess.Popen(check_command, shell=True, cwd=repo, stdout=handle, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        if on_start:
            on_start(process.pid)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return None


def empty_details():
    return {"summaries": [], **{kind: [] for kind in CHANGE_KINDS}}


def run(repo, check_command, log, timeout, env=None, on_start=None, base="HEAD"):
    """Run the full check once. Returns (result, the log's last lines, details). The details hold `summaries` (the
    runner's own summary lines), `changed` (tracked files the command rewrote) and `created` (files it created), all
    lists; both kinds of file are left in place. On a lint failure the lines are the failing step's lines, not the
    log's last lines. `on_start`, when given, is called with the pid of the process group
    the check leads."""
    details = empty_details()
    if full_suite_runs_in_ci(repo):
        return NOT_RUN_CI, "", details
    if check_command is None:
        return NOT_RUN_NO_CHECK, "", details

    env = pinned_interpreter_env(repo, env)
    before = take(repo)
    exit_code = run_check_command(repo, check_command, log, timeout, env, on_start)

    log_path = pathlib.Path(log).resolve()
    for kind, paths in zip(CHANGE_KINDS, changes_since(before), strict=True):
        details[kind] = [path for path in paths if (before["root"] / path).resolve() != log_path]

    output = pathlib.Path(log).read_text(errors="replace")
    tail = "\n".join(output.splitlines()[-TAIL_LINES:])
    all_summaries = runner_summaries(output, limit=None)
    details["summaries"] = all_summaries[:MAX_RUNNER_SUMMARIES]
    if exit_code is None:
        return NOT_RUN_TIMEOUT, tail, details
    if exit_code == 0 and SUMMARY_FAILURE.search("\n".join(all_summaries)):
        return FAILED_EXIT_ZERO, tail_with_failing_tests(output, tail), details
    if exit_code == 0:
        return (PASSED if all_summaries else UNVERIFIED), tail, details

    result, failure_lines = failed_run_result(repo, base, exit_code, output, tail)
    return result, failure_lines, details


def failed_run_result(repo, base, exit_code, output, tail):
    """(result, the lines that show it) for a check that exited non-zero."""
    log_lines = output.splitlines()
    gap = environment_gap(repo, output)
    if gap:
        return f"not run (environment gap: {gap})", tail

    # The command is wrong, not the code, when the missing path did not exist at the diff base either.
    missing = missing_path(log_lines[-TAIL_LINES:])
    if missing:
        missing_path_line, path = missing
        if not existed_at_base(repo, base, path):
            return f"not run (check-command error: {missing_path_line})", tail

    tail = tail_with_failing_tests(output, tail)
    # An undeclared missing module is a code failure here: the change may use a dependency it did not declare.
    if is_setup_fault(exit_code, output, repo, include_missing_modules=False):
        return f"{SETUP_FAULT} (exit {exit_code})", tail

    failing_lines = failing_step_lines(log_lines)
    if any(LINT_RULE_LINE.match(line) for line in failing_lines):
        return f"failed (exit {exit_code})", "\n".join(failing_lines)
    return f"failed (exit {exit_code})", tail


def log_comparison(log_lines):
    """(the normalized failing_step_lines, the normalized lines, the normalized failing-block details) of a log: what a
    head run and a base run are compared on."""
    failing_lines = {normalized_log_line(line) for line in failing_step_lines(log_lines)}
    normalized_lines = {normalized_log_line(line) for line in log_lines}
    return failing_lines, normalized_lines, failing_block_details(log_lines)


def remove_worktree(root, tree):
    """Remove the detached worktree `tree` of the repo at `root`, with its changes."""
    subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(tree)],
                   stdin=subprocess.DEVNULL, capture_output=True)


def sweep_stale_base_trees(root, base_parent, max_age_seconds):
    """Remove the children of `base_parent` last modified over `max_age_seconds` ago (a base run that was killed
    before it cleaned up). Removes only those children, each through `git worktree remove` and then its folder."""
    cutoff = time.time() - max_age_seconds
    for child in base_parent.iterdir():
        try:
            if child.is_symlink() or not child.is_dir() or child.stat().st_mtime > cutoff:
                continue
        except FileNotFoundError:
            continue

        remove_worktree(root, child / "base")
        shutil.rmtree(child, ignore_errors=True)


def base_run_would_test_head(root, repo_path, check_command, env, gate_env):
    """True when a base run would test the head tree: the repo holds an editable or linked install, the command or a
    `gate_env` value names the repo's own path as a whole path, or an inherited import path enters the repo."""
    if holds_editable_install(repo_path, env):
        return True

    own_paths = (str(repo_path), str(root))
    gate_values = (gate_env or {}).values()
    names_repo_path = any(script_utils.names_path(path, text)
                          for path in own_paths for text in (check_command, *gate_values))
    return names_repo_path or import_path_enters_repo(env, own_paths, repo_path)


def link_dependency_folders(repo_path, base_repo):
    """Link the repo's untracked dependency folders into the base tree, where the checkout does not hold them."""
    for folder in UNTRACKED_DEPENDENCY_FOLDERS:
        if (repo_path / folder).is_dir() and not (base_repo / folder).exists():
            (base_repo / folder).symlink_to(repo_path / folder, target_is_directory=True)


def base_run(repo, check_command, log, timeout, env=None, on_start=None, live_trees=None, gate_env=None):
    """The check run in a detached worktree of HEAD, made under the repo's git common dir and removed afterwards,
    with the repo's dependency folders linked in; the log is written to `log`. Returns a BaseRun, or None when the
    base run is not a failure (it passes, timed out, hit a setup fault or an environment gap), the repo holds an
    editable or linked install, the command or a `gate_env` value (the assignments the gate adds, not the inherited
    environment) names the repo's own path as a whole path, or an inherited PYTHONPATH or NODE_PATH entry resolves
    inside the repo (no base run is made: it would test the head tree), or the worktree cannot be made or does not hold
    the repo's folder (an untracked one). The user's
    working tree is never touched. A cache the check writes through a linked folder lands in the user's folder.
    `live_trees`, when given, is a set that holds (repo root, worktree) while the worktree exists, so a signal
    handler can remove it."""
    root = script_utils.repo_root(repo)
    if root is None:
        return None

    repo_path = pathlib.Path(repo).resolve()
    if base_run_would_test_head(root, repo_path, check_command, env, gate_env):
        return None

    common_dir = script_utils.git_output(root, "rev-parse", "--git-common-dir")
    if common_dir is None:
        return None

    base_parent = (pathlib.Path(root) / common_dir / BASE_TREE_FOLDER).resolve()
    base_parent.mkdir(parents=True, exist_ok=True)
    sweep_stale_base_trees(root, base_parent, 2 * timeout)
    with tempfile.TemporaryDirectory(dir=base_parent) as temp:
        tree = pathlib.Path(temp) / "base"
        # The user's post-checkout hook does not fire for the throwaway tree.
        added = subprocess.run(["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", "worktree", "add",
                                "--detach", str(tree), "HEAD"], stdin=subprocess.DEVNULL, capture_output=True)
        if added.returncode != 0:
            return None

        live_tree = (root, tree)
        if live_trees is not None:
            live_trees.add(live_tree)
        try:
            base_repo = tree / repo_path.relative_to(root.resolve())
            # A folder the HEAD tree does not hold (an untracked package) has no copy in the base tree to run in.
            if not base_repo.is_dir():
                return None

            link_dependency_folders(repo_path, base_repo)
            result, _lines, _details = run(base_repo, check_command, log, timeout, env=env, on_start=on_start)
        finally:
            remove_worktree(root, tree)
            if live_trees is not None:
                live_trees.discard(live_tree)

    if not is_failure(result):
        return None

    # The base run's paths name the temp worktree; the head run's name the repo.
    base_log_text = pathlib.Path(log).read_text(errors="replace")
    base_log_text = base_log_text.replace(str(base_repo), str(repo_path)).replace(str(tree), str(root))
    pathlib.Path(log).write_text(base_log_text)
    return BaseRun(result, *log_comparison(base_log_text.splitlines()))


def is_pre_existing(head_log, head_result, base):
    """True when the head run fails as the base run does: the same result (exit code), failing lines that are not
    empty and all fail in the base run too, every detail line inside a failing block is in the base run's failing
    blocks, and no other line new to the head log holds an error marker. When every failing line is a
    `FAILED: <steps>` summary, no line may be new to the log. `base` is from base_run; None when the base run was no
    failure."""
    if base is None or head_result != base.result or not base.failing_lines:
        return False

    head_text = pathlib.Path(head_log).read_text(errors="replace")
    head_lines, head_log_lines, head_details = log_comparison(head_text.splitlines())
    if not head_lines or not head_lines <= base.failing_lines:
        return False
    if not head_details <= base.failing_details:
        return False

    new_lines = head_log_lines - base.log_lines
    # A `FAILED: <steps>` summary names steps, not what failed in them, so a new line anywhere is a new failure.
    if all(FAILED_STEPS_LINE.match(line) for line in head_lines):
        return not new_lines

    return not any(ERROR_MARKER.search(line) for line in new_lines)


def is_failure(result):
    return result.startswith("failed")


def is_unverified(result):
    return result.startswith("unverified")


def summary_text(result, summaries):
    """The summary line's text for a passed or unverified result: the runner's summary lines joined, or `not found`
    when there are none. None for any other result, which carries no summary."""
    if result != PASSED and not is_unverified(result):
        return None
    return SUMMARY_SEPARATOR.join(summaries) or "not found"


def is_setup_fault_result(result):
    return result.startswith(SETUP_FAULT)


def phase_check(repo, check_command, plan, phase):
    """(the command the phase's full check runs, None when the phase's Expected red lines leave out all of it; the
    Expected red entries left out). `plan` is the plan path, relative to the repo or absolute. With no plan or phase
    the command is as given. A plan that cannot be read raises OSError."""
    if not plan or not phase or not check_command:
        return check_command, []

    plan_lines = (pathlib.Path(repo) / plan).read_text().splitlines()
    return expected_red.check_for_phase(check_command, plan_lines, phase)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--plan")
    parser.add_argument("--phase")
    if "--" not in argv:
        parser.error("no command after --")

    separator = argv.index("--")
    args = parser.parse_args(argv[:separator])
    if UNFILLED_LOG_NAME.search(pathlib.Path(args.log).name):
        parser.error(f"--log name {pathlib.Path(args.log).name!r} holds an unfilled placeholder (`...`, `<` or `>`)")
    if bool(args.plan) != bool(args.phase):
        parser.error("--plan and --phase go together")

    command_words = argv[separator + 1:]
    check_command = shlex.join(command_words) if len(command_words) > 1 else "".join(command_words)
    if not check_command:
        parser.error("no command after --")

    try:
        phase_command, left_out = phase_check(args.repo, check_command, args.plan, args.phase)
    except OSError as error:
        parser.error(f"--plan {args.plan}: {error.strerror}")

    declared = check_command == configured_check_command(args.repo)
    scoped = check_scope.command_check_scope(check_command, args.repo) == "targeted"
    if phase_command is None:
        result, tail, details = expected_red.not_run_result(left_out), "", empty_details()
    elif not declared and scoped and not full_suite_runs_in_ci(args.repo):
        result, tail, details = NOT_RUN_SCOPED, "", empty_details()
    else:
        result, tail, details = run(args.repo, phase_command, args.log, args.timeout, base=args.base)
    print(f"full check: {result}")
    for entry in left_out:
        print("expected red: " + expected_red.entry_text(entry))
    summary = summary_text(result, details["summaries"])
    if summary is not None:
        print("summary: " + summary)
    if details["changed"]:
        print("changed by the check: " + ", ".join(details["changed"]))
    if details["rewrote_edited"]:
        print("rewrote edited files: " + ", ".join(details["rewrote_edited"]))
    if details["created"]:
        print("created by the check: " + ", ".join(details["created"]))
    if is_failure(result) or is_setup_fault_result(result):
        print(tail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
