#!/usr/bin/env python3
"""Wait, inside the /code fork, for a background coder or for the review loop and its reviewers.

    python3 ~/.claude/scripts/code/code_wait.py agent <agent id>
    python3 ~/.claude/scripts/code/code_wait.py review [<agent id> <report file>]...
    python3 ~/.claude/scripts/code/code_wait.py review --loop <loop dir> [<agent id> <report file>]...

Nested Agent calls in a fork return at once, and a fork that ends its turn hands back, so the fork waits here instead.
`agent` waits for the subagent's transcript to finish and prints its hand-back report, only a report no earlier wait
printed: a resumed agent's old report is not printed again.
`review` waits for the code_review_start.py process that `code_review_start.py --detach` left. Each `<agent id>
<report file>` pair names a reviewer the fork dispatched for an open request (see reviewer_dispatch.py): the wait
writes each one's report to its file as soon as that reviewer finishes, which is how the reports reach the loop (the
fork has no Write tool). It returns when the loop asks for reviewers no pair answers (`ACTION: dispatch-reviewer`),
when a named reviewer finished with no report (exit 1), or once the loop ends: it prints the loop's output when the
loop left a packet (then exits 1 with a STOP line when the packet's status is fix-removed-change), and otherwise
exits 1 with the reason and the restart step. When that packet is clean (converged, or capped and read as deferred)
and holds finding asks, it also opens a `phase-asks-open` row in the hand-back store and prints the
`phase_asks.py rule` line the session runs to rule on them.
`review --loop <loop dir>` waits the same way on a loop that `review_fix.py launch --detach` started for the /review
or /fix fork: its pid is <loop dir>/loop.pid, and once the loop ends with a packet it prints the packet command to run.
Each call waits at most WAIT_SECONDS, then says to run the same command again.
"""

import dataclasses
import datetime
import json
import os
import pathlib
import re
import sys
from collections.abc import Callable

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review")]
import handback
import handback_store
import loop_transcript
import phase_asks
import process_group
import reviewer_dispatch
import script_utils
import session_registry
import stop_file_names

# The harness moves a Bash call that runs past 180 s to the background, where the fork cannot read its result.
WAIT_SECONDS = 150
POLL_SECONDS = 5
# How long a finished agent's empty report is re-read before it counts as no report.
SETTLE_SECONDS = 3
SETTLE_POLL_SECONDS = 0.25
STILL_WORKING = "Still working. Run the same command again."
NO_REPORT = "The agent finished with no report."
LOOP_GONE = "The review loop process is not running, but these reviewer requests have no report:"
PHASE_RESTART_STEP = "Run this phase's `code_review_start.py ... --detach` line again, then this wait."
PHASE_STOPPED = "Its process was stopped before the loop finished."
LAUNCHED_RESTART = ("Its process was stopped before the loop finished. Run the skill's launch line with --detach "
                    "again, then the wait it prints.")
AGENT_ID = re.compile(r"a[0-9a-f]{16}")
AGENT_ID_FORM = "the agentId an Agent call returned: `a` and 16 hex digits"
PHASE_DIR_NAME = "code-phase"
# One JSON file per agent id: the report line an agent wait printed last. Agent ids are global and the fork's cwd is
# not fixed, so the record sits outside any repo.
AGENT_REPORTS_DIR = pathlib.Path.home() / ".claude" / "state" / "agent-reports"
PID_FILE = "pid"
HANDOFF_FILE = "handoff.txt"  # the phase's hand-off block, in the run folder
PREVIOUS_HANDOFF_FILE = "handoff.prev.txt"  # where phase_start.py moves the last phase's hand-off
REVIEW_OUTPUT = "review.out"
PHASE_RUN_FILE = "run.json"  # the lane and phase of the last started phase review
LOOP_FOLDER_KEY = "loop_dir"  # the key of PHASE_RUN_FILE that holds this phase's loop folder
LOOP_DIR_FILE = "loop-dir"  # holds the path of the running loop's folder, where its reviewer requests go
PREVIOUS_LOOP_DIR_FILE = "loop-dir.prev"  # where phase_start.py moves the last phase's loop-dir
REVIEW_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"
LOOP_FLAG = "--loop"


class UsageError(Exception):
    pass


def agent_transcript(agent_id):
    # The newest transcript of this agent id under any session's subagents folder, or None before it is written.
    transcript_name = script_utils.subagent_transcript_name(agent_id)
    transcripts = list(session_registry.projects_dir().glob(f"*/*/subagents/{transcript_name}"))
    if not transcripts:
        return None
    return max(transcripts, key=lambda transcript: transcript.stat().st_mtime)


def finished_transcript(agent_id):
    """The agent's transcript once it has finished, else None."""
    transcript = agent_transcript(agent_id)
    if transcript is None or not loop_transcript.agent_finished(transcript):
        return None
    return transcript


def settled_agent_read(transcript):
    """The LoopTranscript of a finished agent's transcript.
    The harness marks the agent finished before its last transcript line (the hand-back's result) is on disk, so a
    read with a hand-back call and no result yet, or with no report, is retried for SETTLE_SECONDS."""
    reads = []

    def settled_read():
        read = loop_transcript.LoopTranscript(transcript)
        reads.append(read)
        return not read.handback_pending and bool(report_of(read).strip())

    script_utils.wait_for(settled_read, SETTLE_SECONDS, SETTLE_POLL_SECONDS)
    return reads[-1]


def report_of(read):
    """The message of the last hand-back call a hook did not deny, else the last text, else ""."""
    return read.handback_message or read.last_text or ""


def report_line(read):
    """The transcript line of the report `report_of` returns, -1 when the transcript holds none."""
    if read.handback_message:
        return read.handback_lines[-1]
    if read.last_text_line is None:
        return -1
    return read.last_text_line


def printed_report_file(agent_id):
    return script_utils.state_file_path(AGENT_REPORTS_DIR, agent_id, ".json")


def printed_report(agent_id):
    """{"agent_id", "line", "time"} of the report an earlier wait printed for this agent, {} when none."""
    record_file = printed_report_file(agent_id)
    if not record_file.is_file():
        return {}
    try:
        record = json.loads(record_file.read_text())
        record["line"] = int(record["line"])
        record["time"] = str(record["time"])
    except (ValueError, KeyError, TypeError) as error:
        sys.exit(f"code_wait: {record_file} is not the {{\"agent_id\", \"line\", \"time\"}} JSON object this wait "
                 f"writes ({error!r}); delete it and run this wait again")
    return record


def record_printed_report(agent_id, line):
    record_file = printed_report_file(agent_id)
    record_file.parent.mkdir(parents=True, exist_ok=True)
    record = {"agent_id": agent_id, "line": line, "time": datetime.datetime.now().isoformat(timespec="seconds")}
    script_utils.write_text_atomically(record_file, json.dumps(record) + "\n")


def checked_agent_id(word):
    if not AGENT_ID.fullmatch(word):
        raise UsageError(f"{word!r} is not an agent id; expected {AGENT_ID_FORM}, as its own argument")
    return word


def phase_dir(repo):
    # <git dir>/code-phase, which stays right in a linked worktree, where .git is a file.
    folder = script_utils.git_path(repo, PHASE_DIR_NAME)
    if folder is None:
        sys.exit(f"code_wait: {repo} is not inside a git checkout")
    return folder


def running_review_pid(repo):
    """The pid in <git dir>/code-phase/pid when that process is alive, else None."""
    pid_file = phase_dir(repo) / PID_FILE
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if process_group.pid_is_alive(pid) else None


def loop_dir(repo):
    # The running loop's folder; None before the loop has named it.
    loop_dir_file = phase_dir(repo) / LOOP_DIR_FILE
    try:
        return loop_dir_file.read_text().strip()
    except FileNotFoundError:
        return None


def write_phase_run(repo, lane, phase, loop_folder=None):
    """Records the lane and phase of the phase review that code_review_start.py runs, where the ask rows read them,
    and the folder of its loop when it names one: `code_wait.py review` returns no other folder's packet."""
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    record = {"lane": lane, "phase": phase}
    if loop_folder is not None:
        record[LOOP_FOLDER_KEY] = str(loop_folder)
    script_utils.write_text_atomically(folder / PHASE_RUN_FILE, json.dumps(record) + "\n")


def read_phase_run(repo):
    """{"lane", "phase"} of the phase review in <git dir>/code-phase, {} when no run left the record."""
    run_file = phase_dir(repo) / PHASE_RUN_FILE
    if not run_file.is_file():
        return {}
    try:
        run_info = json.loads(run_file.read_text())
    except ValueError as error:
        sys.exit(f"code_wait: {run_file} is not the {{\"lane\", \"phase\"}} JSON object code_review_start.py writes "
                 f"({error}); delete it and run this wait again")
    if not isinstance(run_info, dict):
        sys.exit(f"code_wait: {run_file} is not the {{\"lane\", \"phase\"}} JSON object code_review_start.py writes "
                 f"(found {type(run_info).__name__}); delete it and run this wait again")
    return run_info


def phase_asks_notice(repo):
    """The lines that tell the session to rule on the finding asks of the phase packet the loop left, after opening
    them in the hand-back store. Empty when the loop left no packet, the packet does not parse, or
    `phase_asks.record_open` opens nothing. Raises what `phase_asks.record_open` raises when the asks cannot be
    opened; `wait_review` fails the wait on it."""
    folder = loop_dir(repo)
    if folder is None:
        return []
    packet_file = pathlib.Path(folder) / reviewer_dispatch.PACKET_FILE
    if not packet_file.is_file():
        return []
    try:
        packet = handback.load(packet_file.read_text())
    except handback.PacketError as error:
        print(f"code_wait: the packet does not parse, so its asks are not opened for ruling: {error.problems}",
              file=sys.stderr)
        return []

    repo_top = script_utils.repo_root(repo)
    if repo_top is None:
        print(f"code_wait: {repo} is not in a work tree, so the packet's asks are not opened for ruling",
              file=sys.stderr)
        return []
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    packet_key = f"{folder}:{packet['iter']}"
    return phase_asks.record_open(session_id, str(repo_top), packet, read_phase_run(repo), packet_key)


@dataclasses.dataclass(frozen=True)
class ReviewRun:
    """The review loop a `review` wait follows: the command that waits on it again, the folder that holds its
    reviewer requests (None before the loop names it), whether it still runs, what to print once it ended ("" when
    it left nothing), the message for an ended loop that left nothing, and how to start it again when its process
    ended before the loop finished."""
    command: str
    loop_folder: Callable[[], str | None]
    running: Callable[[], bool]
    final_output: Callable[[], str]
    no_output: Callable[[], str]
    restart: str
    stop_line: Callable[[], str] = lambda: ""


def phase_review_output(repo):
    # review.out holds code_review_start.py's stdout, which is text even when the loop died with no packet, so only
    # the loop's packet says the loop finished.
    folder = loop_dir(repo)
    if folder is None:
        return ""
    if not (pathlib.Path(folder) / reviewer_dispatch.PACKET_FILE).is_file():
        return ""
    review_output = phase_dir(repo) / REVIEW_OUTPUT
    if not review_output.exists():
        return ""
    return review_output.read_text()


def phase_review(repo):
    """The review code_review_start.py --detach left for the /code fork."""

    def no_output():
        # The loop names its folder after this run starts, so read it when the message is needed. No folder and no
        # process means no loop of this phase started (phase_start.py moved the last one aside), or a detached child
        # died before it wrote its loop folder: the log holds that child's error.
        folder = loop_dir(repo)
        if folder is None and running_review_pid(repo) is None:
            return f"No review of this phase has started. Log of the last start: {phase_dir(repo) / REVIEW_OUTPUT}."
        folder = folder or "<loop dir>"
        return (f"The review loop ended and left no packet in {pathlib.Path(folder) / reviewer_dispatch.PACKET_FILE}. "
                f"Log: {phase_dir(repo) / REVIEW_OUTPUT}. {PHASE_STOPPED}")

    return ReviewRun(REVIEW_COMMAND, lambda: loop_dir(repo), lambda: running_review_pid(repo) is not None,
                     lambda: phase_review_output(repo), no_output, PHASE_RESTART_STEP, lambda: phase_stop_line(repo))


def phase_stop_line(repo):
    """The step line for a phase packet whose status the skill's routes do not cover, or "" for any other packet
    (one that does not parse included: the skill reads it from the printed output)."""
    folder = loop_dir(repo)
    if folder is None:
        return ""
    packet_file = pathlib.Path(folder) / reviewer_dispatch.PACKET_FILE
    try:
        status = handback.parse(packet_file.read_text()).get("status")
    except handback.PacketError:
        return ""
    if status != handback.FIX_REMOVED_CHANGE:
        return ""
    stop_file = phase_dir(repo) / stop_file_names.STOP_FILE
    return (f"STOP ({status}): the fix passes removed half or more of this phase's change. Write the packet's "
            f"`blockers` to {stop_file} and end the run there. The user checks `git diff`; `/code resume` "
            "(with the plan's absolute path when the run has a plan file) then runs this phase's review again.")


def launched_loop_running(folder):
    pid = reviewer_dispatch.loop_pid(folder)
    return pid is not None and process_group.pid_is_alive(pid)


def launched_review_command(folder):
    return f"{REVIEW_COMMAND} {LOOP_FLAG} {folder}"


def launched_review(folder):
    """The review `review_fix.py launch --detach` started in `folder` for the /review or /fix fork."""
    pid_file = pathlib.Path(folder) / reviewer_dispatch.PID_FILE
    if not pid_file.is_file():
        raise UsageError(f"{folder} holds no {reviewer_dispatch.PID_FILE}; expected the loop folder that "
                         "`review_fix.py launch --detach` printed")
    try:
        packet_command = reviewer_dispatch.packet_command(folder)
    except reviewer_dispatch.ManifestError as error:
        raise UsageError(str(error)) from error
    packet_file = pathlib.Path(folder) / reviewer_dispatch.PACKET_FILE

    def final_output():
        if not packet_file.is_file():
            return ""
        return f"The review loop script finished. Run `{packet_command}` now."

    no_output = f"The review loop ended and left no packet in {packet_file}."
    return ReviewRun(launched_review_command(folder), lambda: folder, lambda: launched_loop_running(folder),
                     final_output, lambda: no_output, LAUNCHED_RESTART)


def open_reviewer_requests(run):
    # The loop's reviewer requests that have no report yet.
    folder = run.loop_folder()
    if folder is None:
        return []
    return reviewer_dispatch.pending_requests(folder)


def new_finished_transcript(agent_id, printed):
    # Each poll parses the transcript once; that parse decides both "finished" and "newer than the printed report".
    transcript = agent_transcript(agent_id)
    if transcript is None:
        return None
    read = loop_transcript.LoopTranscript(transcript)
    if not (loop_transcript.finished_by_meta(transcript) or read.handback_lines):
        return None
    if printed and report_line(read) <= printed["line"]:
        return None
    return transcript


def print_still_working(agent_id, printed):
    print(STILL_WORKING)
    transcript = agent_transcript(agent_id)
    if transcript is None or not printed:
        return
    # The stored line is 0-based; editors and Read offsets count from 1.
    print(f"The agent's last report (line {printed['line'] + 1}) was printed by an earlier wait at {printed['time']}. "
          f"This wait prints only a newer report. When the agent was not resumed, read {transcript}.")


def wait_agent(agent_id):
    printed = printed_report(agent_id)
    transcript = script_utils.wait_for(lambda: new_finished_transcript(agent_id, printed), WAIT_SECONDS, POLL_SECONDS)
    if not transcript:
        print_still_working(agent_id, printed)
        return 0

    read = settled_agent_read(transcript)
    report = report_of(read)
    if not report.strip():
        print(f"{NO_REPORT} Transcript: {transcript}")
        return 0
    print(report)
    record_printed_report(agent_id, report_line(read))
    return 0


def reviewer_pairs(run, words):
    """The (agent id, report file) pairs of `review`'s arguments. Each report file must be one the loop's requests
    name."""
    if len(words) % 2:
        raise UsageError(f"`review` takes <agent id> <report file> pairs; got {len(words)} word(s): {words}")
    folder = run.loop_folder()
    requested = set()
    if folder is not None:
        requested = {entry["report_file"] for entry in reviewer_dispatch.all_requests(folder)}
    pairs = []
    for agent_id, report_file in zip(words[::2], words[1::2], strict=True):
        if report_file not in requested:
            raise UsageError(f"{report_file} is no report file of the running loop's requests; "
                             "expected a report file from an `ACTION: dispatch-reviewer` line")
        pairs.append((checked_agent_id(agent_id), report_file))
    return pairs


def write_finished_reports(pairs):
    """Write the report of each named reviewer that has finished and whose report file holds no text yet. Returns
    the lines that name each finished reviewer with no report."""
    empty = []
    for agent_id, report_file in pairs:
        if reviewer_dispatch.report_text(report_file).strip():
            continue
        transcript = finished_transcript(agent_id)
        if transcript is None:
            continue
        read = settled_agent_read(transcript)
        report = report_of(read)
        if not report.strip():
            empty.append(f"- agent {agent_id}; report {report_file}; transcript {transcript}")
            continue
        script_utils.write_text_atomically(pathlib.Path(report_file), report)
    return empty


def unanswered_requests(run, pairs):
    answered = {report_file for _agent_id, report_file in pairs}
    return [entry for entry in open_reviewer_requests(run) if entry["report_file"] not in answered]


def reviewer_dispatch_lines(run, pending):
    return [*reviewer_dispatch.request_lines(pending),
            f"Then run `{run.command} <agentId> <report file>`, with one agentId and its line's report file "
            "for each agent you dispatched, every one written out as its own word."]


def stale_loop_line(repo):
    """The stop text when the loop-dir file names a folder other than the one this phase's code_review_start.py
    recorded in run.json, else "". A run.json with no recorded folder (an older record) is not checked."""
    named = loop_dir(repo)
    recorded = read_phase_run(repo).get(LOOP_FOLDER_KEY)
    if named is None or recorded is None or named == recorded:
        return ""
    record_file = phase_dir(repo) / PHASE_RUN_FILE
    return (f"The loop folder {named} is not the one this phase's review recorded in {record_file} ({recorded}), "
            f"so its packet belongs to another phase's review and is not returned. {PHASE_RESTART_STEP}")


def wait_review(repo, words=(), launched_folder=None):
    if launched_folder is not None:
        return follow_run(repo, launched_review(launched_folder), words, launched_folder)

    stale_line = stale_loop_line(repo)
    if stale_line:
        print(stale_line)
        return 1
    return follow_run(repo, phase_review(repo), words, None)


def follow_run(repo, run, words, launched_folder):
    pairs = reviewer_pairs(run, list(words))
    empty = []

    def next_step():
        empty.extend(write_finished_reports(pairs))
        return bool(empty) or bool(unanswered_requests(run, pairs)) or not run.running()

    if not script_utils.wait_for(next_step, WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    if empty:
        print("\n".join([NO_REPORT, *empty, "Dispatch each of these agents again with the same prompt, then run "
                         f"`{run.command}` with the new agentId in place of the old one."]))
        return 1

    if not run.running():
        code = print_ended_loop(run)
        if code != 0 or launched_folder is not None:
            return code
        try:
            notice = phase_asks_notice(repo)
        except (handback_store.PhaseAskRowError, OSError) as error:
            print(f"code_wait: the finding asks of the phase packet could not be opened for ruling: {error}")
            print(f"Run `{run.command}` again to open them for ruling.")
            return 1
        if notice:
            print("\n".join(notice))
        return code

    pending = unanswered_requests(run, pairs)
    if pending:
        print("\n".join(reviewer_dispatch_lines(run, pending)))
        return 0

    print(STILL_WORKING)
    return 0


def print_ended_loop(run):
    # The loop's own output comes first: a loop that ended may have written a packet, a crash packet included, which
    # says more than a missing process does.
    final_output = run.final_output()
    if final_output.strip():
        print(final_output)
        stop_line = run.stop_line()
        if not stop_line:
            return 0
        print(stop_line)
        return 1

    open_requests = open_reviewer_requests(run)
    if open_requests:
        folder = run.loop_folder()
        print("\n".join([LOOP_GONE, *reviewer_dispatch.request_lines(open_requests)[1:], f"Loop folder: {folder}",
                         run.restart]))
        return 1

    print(f"{run.no_output()} {run.restart}")
    return 1


def review_words(words):
    """(loop folder or None, the pair words) of `review`'s arguments."""
    if words[:1] != [LOOP_FLAG]:
        return None, words
    if len(words) < 2:
        raise UsageError(f"{LOOP_FLAG} needs the loop folder that `review_fix.py launch --detach` printed")
    return words[1], words[2:]


def run(argv):
    if len(argv) == 3 and argv[1] == "agent":
        return wait_agent(checked_agent_id(argv[2]))
    if len(argv) >= 2 and argv[1] == "review":
        launched_folder, pair_words = review_words(argv[2:])
        return wait_review(pathlib.Path.cwd().resolve(), pair_words, launched_folder)
    raise UsageError(f"unknown arguments {argv[1:]}")


def main(argv):
    try:
        return run(argv)
    except UsageError as error:
        print(f"code_wait: {error}\n{__doc__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
