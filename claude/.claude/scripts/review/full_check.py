#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] -- '<command>'

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `failed (exit N)` with the failing tests and the log's last lines
after it, `setup fault (exit N)` with the same when the environment could not run the check (no program, a runner
that cannot start, no package manifest, no test found), `not run (timeout)` when the command runs past the limit,
or `not run (CI)` when the repo's CLAUDE.md holds the line `Full suite: CI` (the command does not run then).
A command past the limit is killed with its whole process group, so no test process outlives the check.
Exit 0, or 1 when the check failed or hit a setup fault.
"""

import argparse
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
from check_output import is_setup_fault, tail_with_failing_tests

FULL_SUITE_IN_CI = "Full suite: CI"
LIST_MARKER = re.compile(r"^\s*[-*]\s+")
PASSED = "passed"
NOT_RUN_CI = "not run (CI)"
NOT_RUN_TIMEOUT = "not run (timeout)"
# The check could not run here: no program, a runner that cannot start, no package manifest, or no test found.
SETUP_FAULT = "setup fault"
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


def run(repo, check_command, log, timeout, env=None, on_start=None):
    """Run the full check once. Returns (result, the log's last lines). `on_start`, when given, is called with the pid
    of the process group the check leads."""
    if full_suite_runs_in_ci(repo):
        return NOT_RUN_CI, ""

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

    output = pathlib.Path(log).read_text(errors="replace")
    tail = "\n".join(output.splitlines()[-TAIL_LINES:])
    if exit_code is None:
        return NOT_RUN_TIMEOUT, tail
    if exit_code == 0:
        return PASSED, tail

    tail = tail_with_failing_tests(output, tail)
    # A missing module is a code failure here: the change may use a dependency it did not declare.
    if is_setup_fault(exit_code, output, repo, include_missing_modules=False):
        return f"{SETUP_FAULT} (exit {exit_code})", tail
    return f"failed (exit {exit_code})", tail


def is_failure(result):
    return result.startswith("failed")


def is_setup_fault_result(result):
    return result.startswith(SETUP_FAULT)


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
    if is_failure(result) or is_setup_fault_result(result):
        print(tail)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
