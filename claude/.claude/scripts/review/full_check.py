#!/usr/bin/env python3
"""full_check.py — the review loop's one full check of a phase, under a time limit.

    full_check.py <repo> --log <path> [--timeout <seconds>] -- '<command>'

Runs the command, given as one quoted word or as plain words, through the shell in the repo, output to the log, and
prints `full check: <result>` first: `passed`, `unverified (exit 0, no runner summary)` when the command exited 0 but
printed no test runner's own summary line, `failed (exit N)` with the failing tests and the log's last lines
after it, `setup fault (exit N)` with the same when the environment could not run the check (no program, a runner
that cannot start, no package manifest, no test found, a package-manager or engine version mismatch), `not run
(timeout)` when the command runs past the limit, or `not run (CI)` when the repo's CLAUDE.md holds the line
`Full suite: CI` (the command does not run then). A `passed` or `unverified` result is followed by `summary: <the
runner summary lines joined with " | ">` or `summary: not found`.
Tracked files the command rewrote and files it created are left in place and named (`changed by the check: <paths>`,
`created by the check: <paths>`). A file that held edits before the check and was rewritten is named on its own line
(`rewrote edited files: <paths>`). Exit 0 with a runner summary that counts failures is a failure.
A command past the limit is killed with its whole process group, so no test process outlives the check.
Exit 0, or 1 when the check failed or hit a setup fault; 2 for a usage error, such as a --log path that still holds
a template placeholder.
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
from test_run_output import MAX_RUNNER_SUMMARIES, runner_summaries
from worktree_snapshot import CHANGE_KINDS, changes_since, take

FULL_SUITE_IN_CI = "Full suite: CI"
LIST_MARKER = re.compile(r"^\s*[-*]\s+")
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


def run(repo, check_command, log, timeout, env=None, on_start=None):
    """Run the full check once. Returns (result, the log's last lines, details). The details hold `summaries` (the
    runner's own summary lines), `changed` (tracked files the command rewrote) and `created` (files it created), all
    lists; both kinds of file are left in place. `on_start`, when given, is called with the pid of the process group
    the check leads."""
    details = {"summaries": [], **{kind: [] for kind in CHANGE_KINDS}}
    if full_suite_runs_in_ci(repo):
        return NOT_RUN_CI, "", details

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

    tail = tail_with_failing_tests(output, tail)
    # A missing module is a code failure here: the change may use a dependency it did not declare.
    if is_setup_fault(exit_code, output, repo, include_missing_modules=False):
        return f"{SETUP_FAULT} (exit {exit_code})", tail, details
    return f"failed (exit {exit_code})", tail, details


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


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    if "--" not in argv:
        parser.error("no command after --")

    separator = argv.index("--")
    args = parser.parse_args(argv[:separator])
    if UNFILLED_LOG_NAME.search(pathlib.Path(args.log).name):
        parser.error(f"--log name {pathlib.Path(args.log).name!r} holds an unfilled placeholder (`...`, `<` or `>`)")

    command_words = argv[separator + 1:]
    check_command = shlex.join(command_words) if len(command_words) > 1 else "".join(command_words)
    if not check_command:
        parser.error("no command after --")

    result, tail, details = run(args.repo, check_command, args.log, args.timeout)
    print(f"full check: {result}")
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
