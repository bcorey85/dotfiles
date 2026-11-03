#!/usr/bin/env python3
"""The hand-off of a review round to the main session, which runs the reviewers as its own subagents.

    reviewer_dispatch.py wait <loop dir>

In `--reviewers main` mode the review loop writes each reviewer's prompt to a file and the round's manifest to
<loop dir>/reviewer-requests/round-<n>.json ({"round", "requests": [{"role", "agent", "prompt_file",
"report_file"}]}), then waits until every report file holds text. The main session dispatches each agent, writes
each report verbatim to its report file, and runs `wait` again.

`wait` returns at the next step: it prints `ACTION: dispatch-reviewer` and one line per request that has no report
yet, or, once the loop process (pid in <loop dir>/loop.pid) has ended, the line that says to read the packet.
"""
import argparse
import json
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils

REQUESTS_FOLDER = "reviewer-requests"
PID_FILE = "loop.pid"
POLL_SECONDS = 2.0
DISPATCH_ACTION = "dispatch-reviewer"
WAIT_COMMAND = "python3 ~/.claude/scripts/review/reviewer_dispatch.py wait"
PACKET_COMMAND = "python3 ~/.claude/scripts/review/review_fix.py packet --skill review"


class ManifestError(Exception):
    pass


def requests_dir(loop_dir):
    return pathlib.Path(loop_dir) / REQUESTS_FOLDER


def report_text(report_file):
    """The report's text, or "" while the main session has not written it."""
    try:
        return pathlib.Path(report_file).read_text()
    except FileNotFoundError:
        return ""


def write_round(loop_dir, round_number, requests):
    """Writes each (role, agent, prompt) prompt file and the round's manifest, the manifest last. Returns the
    manifest's request list."""
    folder = requests_dir(loop_dir)
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for role, agent, prompt in requests:
        prompt_file = folder / f"{role}.prompt.md"
        prompt_file.write_text(prompt)
        report_file = folder / f"{role}.report.md"
        entries.append({"role": role, "agent": agent, "prompt_file": str(prompt_file),
                        "report_file": str(report_file)})
    manifest = {"round": round_number, "requests": entries}
    script_utils.write_text_atomically(folder / f"round-{round_number}.json", json.dumps(manifest, indent=2) + "\n")
    return entries


def request_round(loop_dir, round_number, requests, timeout, poll=POLL_SECONDS):
    """Hands the round's reviewers to the main session and waits for their reports. Returns [(text, wall seconds)]
    in request order. Raises RuntimeError when a report is still missing after `timeout` seconds."""
    entries = write_round(loop_dir, round_number, requests)
    started = time.time()
    walls = {}
    while True:
        for entry in entries:
            if entry["role"] in walls:
                continue
            if report_text(entry["report_file"]).strip():
                walls[entry["role"]] = round(time.time() - started, 1)
        if len(walls) == len(entries):
            return [(report_text(entry["report_file"]), walls[entry["role"]]) for entry in entries]

        if time.time() - started > timeout:
            missing = ", ".join(entry["report_file"] for entry in entries if entry["role"] not in walls)
            raise RuntimeError(f"the main session wrote no reviewer report within {timeout} s: {missing}")
        time.sleep(poll)


def read_manifest(manifest_path):
    """One manifest's request list. Raises ManifestError on a file that is not the manifest form."""
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as error:
        raise ManifestError(f"{manifest_path}: not JSON ({error}); expected {{\"round\", \"requests\"}}") from error

    requests = manifest.get("requests") if isinstance(manifest, dict) else None
    if not isinstance(requests, list):
        raise ManifestError(f"{manifest_path}: no \"requests\" list; expected {{\"round\", \"requests\"}}")
    for entry in requests:
        if not isinstance(entry, dict) or not {"role", "agent", "prompt_file", "report_file"} <= entry.keys():
            raise ManifestError(f"{manifest_path}: a request lacks role, agent, prompt_file or report_file")
    return requests


def pending_requests(loop_dir):
    """Every request of every round whose report file holds no text yet."""
    folder = requests_dir(loop_dir)
    if not folder.is_dir():
        return []
    pending = []
    for manifest_path in sorted(folder.glob("round-*.json")):
        requests = read_manifest(manifest_path)
        pending += [entry for entry in requests if not report_text(entry["report_file"]).strip()]
    return pending


def dispatch_lines(loop_dir, pending):
    lines = [f"ACTION: {DISPATCH_ACTION}"]
    lines += [f"- agent {entry['agent']}; prompt {entry['prompt_file']}; report {entry['report_file']}"
              for entry in pending]
    lines.append(f"Then run `{WAIT_COMMAND} {loop_dir}` in the background.")
    return lines


def wait_for_step(loop_dir, is_running, poll=POLL_SECONDS):
    """Waits until the loop asks for reviewers or ends. Returns the dispatch lines, or None once the loop has ended
    with no request open."""
    while True:
        pending = pending_requests(loop_dir)
        if pending:
            return dispatch_lines(loop_dir, pending)
        if not is_running():
            return None
        time.sleep(poll)


def pid_is_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_wait(loop_dir):
    pid_file = pathlib.Path(loop_dir) / PID_FILE
    try:
        pid = int(pid_file.read_text().strip())
    except (FileNotFoundError, ValueError) as error:
        print(f"reviewer_dispatch: {pid_file} holds no loop pid ({error}); expected the pid that "
              "`review_fix.py launch` wrote. Run `launch` again.", file=sys.stderr)
        return 2

    lines = wait_for_step(loop_dir, lambda: pid_is_running(pid))
    if lines is None:
        lines = [f"The review loop script finished. Run `{PACKET_COMMAND}` now."]
    print("\n".join(lines))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    wait = commands.add_parser("wait", help="wait for the loop's next reviewer request or its end")
    wait.add_argument("loop_dir")
    args = parser.parse_args(argv)
    try:
        return command_wait(args.loop_dir)
    except ManifestError as error:
        print(f"reviewer_dispatch: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
