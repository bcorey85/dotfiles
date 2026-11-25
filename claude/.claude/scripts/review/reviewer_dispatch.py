#!/usr/bin/env python3
"""The hand-off of a review round to the main session, which runs the reviewers as its own subagents.

    reviewer_dispatch.py wait <loop dir>

In `--reviewers main` mode the review loop writes each reviewer's prompt to a file and the round's manifest to
<loop dir>/reviewer-requests/round-<n>.json ({"round", "requests": [{"round", "role", "agent",
"prompt_file", "report_file"}]}), then waits until every report file holds text. The main session dispatches each
agent, writes each report verbatim to its report file, and runs `wait` again.

`wait` returns at the next step: it prints `ACTION: dispatch-reviewer`, a `round <n>:` heading per round and one
`- round <n>: <role>; agent ...` line per request that has no report yet, or, once the loop process (pid in
<loop dir>/loop.pid) has ended, the line that says to read the packet, after the `LOOP_GONE` heading and the open
request lines when a request was left with no report.
"""
import argparse
import itertools
import json
import pathlib
import shlex
import sys
import time
from typing import NamedTuple

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / "lib"), str(SCRIPTS_DIR / "review")]
import script_utils
from age_text import age_text
from process_group import pid_is_alive
from review_fix_state import REVIEW_FIX_COMMAND
from review_loop_prompt_file import PLAN_KEY, PROMPT_FILE, REPO_KEY, PromptFileError, read_prompt

REQUESTS_FOLDER = "reviewer-requests"
PID_FILE = "loop.pid"
PACKET_FILE = "packet.txt"
POLL_SECONDS = 2.0
DISPATCH_ACTION = "dispatch-reviewer"
WAIT_COMMAND = "python3 ~/.claude/scripts/review/reviewer_dispatch.py wait"
# The reviewer agents have no Write tool, so the prompt asks for no file.
AGENT_PROMPT = "Read {prompt_file} whole and do that task."
# The `wait` route runs no writer: the main session writes each report itself.
SESSION_WRITES_NOTE = "(the main session writes the reviewer's reply verbatim to it; the reviewer writes no file)"
PACKET_COMMAND = f"{REVIEW_FIX_COMMAND} packet"
LOOP_GONE = "The review loop process is not running, but these reviewer requests have no report:"
# The packet arguments and the relaunch flags of a run `review_fix.py launch` started:
# {"packet_args": [...], "relaunch_args": [...], "user_ruled": [<finding text>...]}. `user_ruled` may be missing
# from older records.
LAUNCH_FILE = "launch.json"
PACKET_ARGS_KEY = "packet_args"
SKILL_FLAG = "--skill"
# Also: "branch" (the repo's branch at launch), "launched_at" (epoch seconds) and "detach" (true for a code fork's
# `--detach` launch); the session-start notice reads them.
LAUNCH_BRANCH_KEY = "branch"
LAUNCH_TIME_KEY = "launched_at"
LAUNCH_DETACH_KEY = "detach"
# `review_fix.py launch` keeps each run at <git path of LAUNCH_STATE_NAME>/loop-script/<agent id>.
LAUNCH_STATE_NAME = "review-script"
LOOP_FOLDER = "loop-script"


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


def write_round(loop_dir, round_number, requests, model=""):
    """Writes each (role, agent, prompt) prompt file and the round's manifest, the manifest last. Returns the
    manifest's request list. A model names the model every request runs on."""
    folder = requests_dir(loop_dir)
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    taken = set()
    for given_role, agent, prompt in requests:
        # A large diff splits one agent over several dispatches that share a role. Number the repeats, or their
        # files collide and the wait counts one report for two requests and never finishes.
        role = given_role
        copy_number = 1
        while role in taken:
            copy_number += 1
            role = f"{given_role}-{copy_number}"
        taken.add(role)
        prompt_file = folder / f"{role}.prompt.md"
        prompt_file.write_text(prompt)
        report_file = folder / f"{role}.report.md"
        entry = {"round": round_number, "role": role, "agent": agent, "prompt_file": str(prompt_file),
                 "report_file": str(report_file)}
        if model:
            entry["model"] = model
        entries.append(entry)
    manifest = {"round": round_number, "requests": entries}
    script_utils.write_text_atomically(folder / f"round-{round_number}.json", json.dumps(manifest, indent=2) + "\n")
    return entries


def request_round(loop_dir, round_number, requests, timeout, poll=POLL_SECONDS, model=""):
    """Hands the round's reviewers to the main session and waits for their reports. Returns [(text, wall seconds)]
    in request order. Raises RuntimeError when a report is still missing after `timeout` seconds."""
    entries = write_round(loop_dir, round_number, requests, model)
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
    # A manifest written before entries carried their round gives its entries the manifest's round.
    round_number = manifest.get("round")
    if not isinstance(round_number, int) or isinstance(round_number, bool):
        raise ManifestError(f"{manifest_path}: \"round\" is {round_number!r}; expected a whole number")
    return [{"round": round_number, **entry} for entry in requests]


def manifest_round(manifest_path):
    """The round number in a `round-<n>.json` file name, so round 10 sorts after round 9."""
    number = manifest_path.stem.removeprefix("round-")
    if not number.isdecimal():
        raise ManifestError(f"{manifest_path}: the file name holds {number!r}; expected round-<whole number>.json")
    return int(number)


def all_requests(loop_dir):
    """Every request of every round."""
    folder = requests_dir(loop_dir)
    if not folder.is_dir():
        return []
    requests = []
    for manifest_path in sorted(folder.glob("round-*.json"), key=manifest_round):
        requests += read_manifest(manifest_path)
    return requests


def pending_requests(loop_dir):
    """Every request of every round whose report file holds no text yet."""
    return [entry for entry in all_requests(loop_dir) if not report_text(entry["report_file"]).strip()]


def request_lines(pending, report_writer_note):
    """The `ACTION: dispatch-reviewer` line, then per round a heading line and one line per open request of that
    round, for any caller's wait command.

    `report_writer_note` names who writes each report file; it must match the caller's next step."""
    lines = [f"ACTION: {DISPATCH_ACTION}"]
    first_open_round = min((entry["round"] for entry in pending), default=1)
    for round_number, group in itertools.groupby(pending, key=lambda entry: entry["round"]):
        entries = list(group)
        heading = f"round {round_number}: dispatch these {len(entries)} reviewer(s) now"
        # Only the oldest open round can say its predecessors are answered; a later round with an older one open cannot.
        if round_number > 1 and round_number == first_open_round:
            heading += "; earlier rounds' reports are already in"
        lines.append(heading)
        for entry in entries:
            prompt = AGENT_PROMPT.format(prompt_file=entry["prompt_file"])
            line = f"- round {round_number}: {entry['role']}; agent {entry['agent']}; prompt \"{prompt}\""
            if entry.get("model"):
                line += f"; model {entry['model']}"
            line += f"; report {entry['report_file']} {report_writer_note}"
            lines.append(line)
    return lines


def open_request_lines(pending):
    """One line per open request for a loop that is gone: the round, role, agent and report file, with no prompt to
    dispatch."""
    return [f"- round {entry['round']}: {entry['role']}; agent {entry['agent']}; report {entry['report_file']}"
            for entry in pending]


def dispatch_lines(loop_dir, pending):
    return [*request_lines(pending, SESSION_WRITES_NOTE), f"Then run `{WAIT_COMMAND} {loop_dir}` in the background."]


def wait_for_step(loop_dir, is_running, poll=POLL_SECONDS):
    """Waits until the loop asks for reviewers or ends. Returns the dispatch lines, the open-request lines when the
    loop is gone with a request still open (the heading, the requests and the packet command; no order to dispatch,
    no wait command), or None once the loop has ended with no request open."""
    while True:
        running = is_running()
        pending = pending_requests(loop_dir)
        if pending and running:
            return dispatch_lines(loop_dir, pending)
        if pending:
            return [LOOP_GONE, *open_request_lines(pending), f"Run `{packet_command(loop_dir)}` now."]
        if not running:
            return None
        time.sleep(poll)


def loop_pid(loop_dir):
    """The pid in <loop dir>/loop.pid, or None when the file is missing or holds no number."""
    try:
        return int((pathlib.Path(loop_dir) / PID_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def live_loops(loop_root):
    """(loop dir, pid) of each folder under loop_root whose loop.pid names a running process, in folder order. A
    missing loop_root yields nothing."""
    loop_root = pathlib.Path(loop_root)
    if not loop_root.is_dir():
        return
    for loop_dir in sorted(loop_root.iterdir()):
        pid = loop_pid(loop_dir)
        if pid is None or not pid_is_alive(pid):
            continue
        yield loop_dir, pid


class LoopLaunch(NamedTuple):
    """What a loop's launch record says about where and when it started. `branch` is None for a record that
    predates the field or when there is no launch record, and "" for a launch from a detached HEAD."""
    branch: str | None
    launched_at: float
    detached: bool


class LaunchNotice(NamedTuple):
    """`dispatch`: the lines that order a dispatch. `left_out`: one line per waiting loop of another
    branch, or launched detached for a code fork, with no ACTION."""
    dispatch: list
    left_out: list


def loop_launch(loop_dir):
    """The launch facts of a loop. A record or an older loop with no launch time reads its start from loop.pid."""
    launch_file = pathlib.Path(loop_dir) / LAUNCH_FILE
    branch, launched_at, detached = None, None, False
    if launch_file.is_file():
        record = read_launch_file(launch_file)
        branch = record.get(LAUNCH_BRANCH_KEY)
        launched_at = record.get(LAUNCH_TIME_KEY)
        detached = record.get(LAUNCH_DETACH_KEY, False)
    if branch is not None and not isinstance(branch, str):
        raise ManifestError(f"{launch_file}: {LAUNCH_BRANCH_KEY} is {branch!r}; expected a string")
    if not isinstance(detached, bool):
        raise ManifestError(f"{launch_file}: {LAUNCH_DETACH_KEY} is {detached!r}; expected true or false")
    if launched_at is not None and (isinstance(launched_at, bool) or not isinstance(launched_at, (int, float))):
        raise ManifestError(f"{launch_file}: {LAUNCH_TIME_KEY} is {launched_at!r}; expected a number")
    if launched_at is None:
        launched_at = (pathlib.Path(loop_dir) / PID_FILE).stat().st_mtime
    return LoopLaunch(branch, launched_at, detached)


def left_out_reason(launch, current_branch):
    """Why a waiting loop is not this repo branch's to dispatch, or None when it is. A record with no branch, or a
    detached HEAD at launch or now, leaves the branch test out."""
    if launch.detached:
        return "it was launched detached for a code fork, where `code_wait.py review` writes its reports"
    if launch.branch and current_branch and launch.branch != current_branch:
        return f"it belongs to branch {launch.branch}, and this repo is on {current_branch}"
    return None


def branch_label(branch):
    """How a launch record's branch reads in the notice."""
    if branch is None:
        return "unknown"
    if branch == "":
        return "detached HEAD"
    return branch


def waiting_launch_lines(repo, now=None):
    """The notice for every `launch` run of repo whose loop still runs and waits on a reviewer report: dispatch
    lines for a loop of this branch, one line with no ACTION for each other loop. Each line shows the loop's age and
    branch."""
    state_dir = script_utils.git_path(repo, LAUNCH_STATE_NAME)
    if state_dir is None:
        return LaunchNotice([], [])
    now = time.time() if now is None else now
    current_branch = script_utils.current_branch(repo)
    notice = LaunchNotice([], [])
    for loop_dir, _pid in live_loops(state_dir / LOOP_FOLDER):
        pending = pending_requests(loop_dir)
        if not pending:
            continue
        launch = loop_launch(loop_dir)
        facts = f"{age_text(now - launch.launched_at)} old, branch {branch_label(launch.branch)}"
        reason = left_out_reason(launch, current_branch)
        if reason:
            notice.left_out.append(f"Left out: loop {loop_dir.name} ({facts}): {reason}. Dispatch nothing for it.")
            continue
        notice.dispatch.append(f"Loop {loop_dir.name} ({facts}):")
        notice.dispatch.extend(dispatch_lines(loop_dir, pending))
    return notice


_REQUIRED = object()


def read_launch_file(launch_file):
    """The launch record in launch_file as a dict. Raises ManifestError naming the file when it is unreadable, not
    JSON, or not a JSON object."""
    try:
        record = json.loads(pathlib.Path(launch_file).read_text())
    except (OSError, ValueError) as error:
        raise ManifestError(f"{launch_file}: {error!r}; expected a launch record (a JSON object)") from error
    if not isinstance(record, dict):
        raise ManifestError(f"{launch_file}: the record is {record!r}; expected a launch record (a JSON object)")
    return record


def read_launch_record(launch_file, key, *, default=_REQUIRED):
    """The value of `key` in a launch record. Raises ManifestError naming the file when it is unreadable or lacks
    the key, unless the caller passes `default=` for a key an older record may lack."""
    try:
        record = read_launch_file(launch_file)
    except ManifestError as error:
        raise ManifestError(f"{error} (reading {key})") from error
    if default is _REQUIRED:
        if key not in record:
            raise ManifestError(f"{launch_file}: no {key}; expected a launch record with {key}")
        return record[key]
    return record.get(key, default)


def read_string_list(launch_file, key, *, default=_REQUIRED):
    """The value of `key` in a launch record. Raises ManifestError naming the file unless it is a list of strings."""
    value = read_launch_record(launch_file, key, default=default)
    if not script_utils.is_string_list(value):
        raise ManifestError(f"{launch_file}: {key} is {value!r}; expected a list of strings")
    return value


def packet_command(loop_dir):
    """The packet command of the run: `packet` plus the arguments `launch` saved in <loop dir>/launch.json, or
    `--skill review` for a run with no such file (one /code started)."""
    launch_file = pathlib.Path(loop_dir) / LAUNCH_FILE
    packet_args = [SKILL_FLAG, "review"]
    if launch_file.is_file():
        packet_args = read_string_list(launch_file, PACKET_ARGS_KEY)
    packet_args = [*packet_args, *plan_arguments(loop_dir)]
    return " ".join([PACKET_COMMAND, shlex.join(packet_args)])


def plan_arguments(loop_dir):
    """`--plan <path>` for the plan the loop's prompt header names (a /code run, or a /review launch with a plan,
    writes one), so `packet` reads the plan's standing rulings; [] when the run has no prompt file or its header
    names no plan."""
    prompt_file = pathlib.Path(loop_dir) / PROMPT_FILE
    if not prompt_file.is_file():
        return []
    try:
        header, _handoff = read_prompt(prompt_file)
    except PromptFileError as error:
        raise ManifestError(f"{prompt_file}: {error}") from error
    plan, repo = header.get(PLAN_KEY), header.get(REPO_KEY)
    if not plan or not repo:
        return []
    return ["--plan", str(pathlib.Path(repo) / plan)]


def command_wait(loop_dir):
    pid_file = pathlib.Path(loop_dir) / PID_FILE
    try:
        pid = int(pid_file.read_text().strip())
    except (FileNotFoundError, ValueError) as error:
        print(f"reviewer_dispatch: {pid_file} holds no loop pid ({error}); expected the pid that "
              "`review_fix.py launch` wrote. Run `launch` again.", file=sys.stderr)
        return 2

    lines = wait_for_step(loop_dir, lambda: pid_is_alive(pid))
    if lines is None:
        lines = [f"The review loop script finished. Run `{packet_command(loop_dir)}` now."]
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
