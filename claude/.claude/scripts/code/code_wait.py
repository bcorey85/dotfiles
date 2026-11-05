#!/usr/bin/env python3
"""Wait, inside the /code fork, for a background coder or for the review loop and its reviewers.

    python3 ~/.claude/scripts/code/code_wait.py agent <agent id>
    python3 ~/.claude/scripts/code/code_wait.py review [<agent id> <report file>]...

Nested Agent calls in a fork return at once, and a fork that ends its turn hands back, so the fork waits here instead.
`agent` waits for the subagent's transcript to finish and prints its hand-back report.
`review` waits for the code_review_start.py process that `code_review_start.py --detach` left. Each `<agent id>
<report file>` pair names a reviewer the fork dispatched for an open request (see reviewer_dispatch.py): the wait
writes each one's report to its file as soon as that reviewer finishes, which is how the reports reach the loop (the
fork has no Write tool). It returns when the loop asks for reviewers no pair answers (`ACTION: dispatch-reviewer`),
when a named reviewer finished with no report (exit 1), or with the loop's output once it ends.
Each call waits at most WAIT_SECONDS, then says to run the same command again.
"""

import os
import pathlib
import re
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review")]
import loop_transcript
import reviewer_dispatch
import script_utils

PROJECTS = pathlib.Path.home() / ".claude" / "projects"
# The harness moves a Bash call that runs past 180 s to the background, where the fork cannot read its result.
WAIT_SECONDS = 150
POLL_SECONDS = 5
STILL_WORKING = "Still working. Run the same command again."
NO_REPORT = "The agent finished with no report."
AGENT_ID = re.compile(r"a[0-9a-f]{16}")
AGENT_ID_FORM = "the agentId an Agent call returned: `a` and 16 hex digits"
PHASE_DIR_NAME = "code-phase"
PID_FILE = "pid"
REVIEW_OUTPUT = "review.out"
LOOP_DIR_FILE = "loop-dir"  # holds the path of the running loop's folder, where its reviewer requests go
REVIEW_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"


class UsageError(Exception):
    pass


def agent_transcript(agent_id):
    # The newest transcript of this agent id under any session's subagents folder, or None before it is written.
    transcripts = list(PROJECTS.glob(f"*/*/subagents/{script_utils.subagent_transcript_name(agent_id)}"))
    if not transcripts:
        return None
    return max(transcripts, key=lambda transcript: transcript.stat().st_mtime)


def finished_transcript(agent_id):
    """The agent's transcript once it has finished, else None."""
    transcript = agent_transcript(agent_id)
    if transcript is None or not loop_transcript.agent_finished(transcript):
        return None
    return transcript


def agent_report(transcript):
    # The message of the agent's last hand-back call a hook did not deny, else its last text, else "".
    read = loop_transcript.LoopTranscript(transcript)
    return read.handback_message or read.last_text or ""


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


def review_running(repo):
    pid_file = phase_dir(repo) / PID_FILE
    try:
        os.kill(int(pid_file.read_text().strip()), 0)
    except (OSError, ValueError):
        return False
    return True


def loop_dir(repo):
    # The running loop's folder; None before the loop has named it.
    loop_dir_file = phase_dir(repo) / LOOP_DIR_FILE
    try:
        return loop_dir_file.read_text().strip()
    except FileNotFoundError:
        return None


def open_reviewer_requests(repo):
    # The running loop's reviewer requests that have no report yet.
    folder = loop_dir(repo)
    if folder is None:
        return []
    return reviewer_dispatch.pending_requests(folder)


def wait_agent(agent_id):
    if not script_utils.wait_for(lambda: finished_transcript(agent_id), WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    transcript = agent_transcript(agent_id)
    report = agent_report(transcript)
    if not report.strip():
        print(f"{NO_REPORT} Transcript: {transcript}")
        return 0
    print(report)
    return 0


def reviewer_pairs(repo, words):
    """The (agent id, report file) pairs of `review`'s arguments. Each report file must be one the loop's requests
    name."""
    if len(words) % 2:
        raise UsageError(f"`review` takes <agent id> <report file> pairs; got {len(words)} word(s): {words}")
    folder = loop_dir(repo)
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
        report = agent_report(transcript)
        if not report.strip():
            empty.append(f"- agent {agent_id}; report {report_file}; transcript {transcript}")
            continue
        script_utils.write_text_atomically(pathlib.Path(report_file), report)
    return empty


def unanswered_requests(repo, pairs):
    answered = {report_file for _agent_id, report_file in pairs}
    return [entry for entry in open_reviewer_requests(repo) if entry["report_file"] not in answered]


def reviewer_dispatch_lines(pending):
    return [*reviewer_dispatch.request_lines(pending),
            f"Then run `{REVIEW_COMMAND} <agentId> <report file>`, with one agentId and its line's report file "
            "for each agent you dispatched, every one written out as its own word."]


def wait_review(repo, words=()):
    pairs = reviewer_pairs(repo, list(words))
    empty = []

    def next_step():
        empty.extend(write_finished_reports(pairs))
        return bool(empty) or bool(unanswered_requests(repo, pairs)) or not review_running(repo)

    if not script_utils.wait_for(next_step, WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    if empty:
        print("\n".join([NO_REPORT, *empty, "Dispatch each of these agents again with the same prompt, then run "
                         f"`{REVIEW_COMMAND}` with the new agentId in place of the old one."]))
        return 1

    pending = unanswered_requests(repo, pairs)
    if pending:
        print("\n".join(reviewer_dispatch_lines(pending)))
        return 0

    review_output = phase_dir(repo) / REVIEW_OUTPUT
    print(review_output.read_text() if review_output.exists() else "No review output was written.")
    return 0


def run(argv):
    if len(argv) == 3 and argv[1] == "agent":
        return wait_agent(checked_agent_id(argv[2]))
    if len(argv) >= 2 and argv[1] == "review":
        return wait_review(pathlib.Path.cwd().resolve(), argv[2:])
    raise UsageError(f"unknown arguments {argv[1:]}")


def main(argv):
    try:
        return run(argv)
    except UsageError as error:
        print(f"code_wait: {error}\n{__doc__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
