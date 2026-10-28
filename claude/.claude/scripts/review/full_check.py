#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] -- '<command>'

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `failed (exit N)` with the log's last lines after it,
`not run (timeout)` when the command runs past the limit, or `not run (CI)` when the repo's CLAUDE.md holds the line
`Full suite: CI` (the command does not run then). A command past the limit is killed with its whole process group,
so no test process outlives the check. A repo with a `.python-version` file runs the command with the pyenv shims
first on PATH. A failed check whose log says `No module named X`, for an X that is not a top-level package of the
repo, prints `not run (environment gap: No module named 'X')`.
Exit 0, or 1 when the check failed.
"""

import argparse
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys

FULL_SUITE_IN_CI = "Full suite: CI"
LIST_MARKER = re.compile(r"^\s*[-*]\s+")
PASSED = "passed"
NOT_RUN_CI = "not run (CI)"
NOT_RUN_TIMEOUT = "not run (timeout)"
MISSING_MODULE = re.compile(r"No module named '?([A-Za-z_][\w.]*)'?")
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


def environment_gap(repo, log_text):
    """The `No module named 'X'` line of a failed check whose X is not a top-level package of the repo, or None."""
    for found in MISSING_MODULE.finditer(log_text):
        module = found.group(1)
        top_level = module.split(".")[0]
        repo_path = pathlib.Path(repo)
        own_paths = [repo_path / top_level, repo_path / f"{top_level}.py", repo_path / "src" / top_level]
        if not any(path.exists() for path in own_paths):
            return f"No module named '{module}'"
    return None


def run(repo, check_command, log, timeout, env=None, on_start=None):
    """Run the full check once. Returns (result, the log's last lines). `on_start`, when given, is called with the pid
    of the process group the check leads."""
    if full_suite_runs_in_ci(repo):
        return NOT_RUN_CI, ""

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
