#!/usr/bin/env python3
"""Wait, inside the /code fork, for a background coder or reviewer, or for the review loop.

    python3 ~/.claude/scripts/code/code_wait.py agent <agent id> [--report-file <file>]
    python3 ~/.claude/scripts/code/code_wait.py review

Nested Agent calls in a fork return at once, and a fork that ends its turn hands back, so the fork waits here instead.
`agent` waits for the subagent's transcript to finish and prints its hand-back report; with `--report-file` it also
writes the report to that file, which is how a reviewer's report reaches the review loop (the fork has no Write tool).
`review` waits for the code_review_start.py process that `code_review_start.py --detach` left: it prints
`ACTION: dispatch-reviewer` and the open reviewer requests when the loop asks for reviewers (see reviewer_dispatch.py),
else the loop's output once it ends. Each call waits at most WAIT_SECONDS, under the fork's 600-second Bash timeout,
then says to run the same command again.
"""

import os
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review")]
import loop_transcript
import reviewer_dispatch
import script_utils

PROJECTS = pathlib.Path.home() / ".claude" / "projects"
WAIT_SECONDS = 540
POLL_SECONDS = 5
STILL_WORKING = "Still working. Run the same command again, with the Bash timeout set to 600000."
NO_REPORT = "The agent finished with no report."
PHASE_DIR_NAME = "code-phase"
PID_FILE = "pid"
REVIEW_OUTPUT = "review.out"
LOOP_DIR_FILE = "loop-dir"  # holds the path of the running loop's folder, where its reviewer requests go
AGENT_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py agent"
REVIEW_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"


def agent_transcript(agent_id):
    # The newest transcript of this agent id under any session's subagents folder, or None before it is written.
    transcripts = list(PROJECTS.glob(f"*/*/subagents/{script_utils.subagent_transcript_name(agent_id)}"))
    if not transcripts:
        return None
    return max(transcripts, key=lambda transcript: transcript.stat().st_mtime)


def agent_report(transcript):
    # The message of the agent's last hand-back call a hook did not deny, else its last text, else "".
    read = loop_transcript.LoopTranscript(transcript)
    return read.handback_message or read.last_text or ""


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


def open_reviewer_requests(repo):
    # The running loop's reviewer requests that have no report yet; none before the loop has named its folder.
    loop_dir_file = phase_dir(repo) / LOOP_DIR_FILE
    try:
        loop_dir = loop_dir_file.read_text().strip()
    except FileNotFoundError:
        return []
    return reviewer_dispatch.pending_requests(loop_dir)


def wait_agent(agent_id, report_file=None):
    def finished():
        transcript = agent_transcript(agent_id)
        return transcript is not None and loop_transcript.agent_finished(transcript)

    if not script_utils.wait_for(finished, WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    transcript = agent_transcript(agent_id)
    report = agent_report(transcript)
    if not report.strip():
        print(f"{NO_REPORT} Transcript: {transcript}")
        return 1 if report_file else 0

    if report_file:
        script_utils.write_text_atomically(pathlib.Path(report_file), report)
    print(report)
    return 0


def reviewer_dispatch_lines(pending):
    return [*reviewer_dispatch.request_lines(pending),
            f"Then, for each agent, run `{AGENT_COMMAND} <agentId> --report-file <its report file>`, and then "
            f"`{REVIEW_COMMAND}`, each with the Bash timeout set to 600000."]


def wait_review(repo):
    def next_step():
        return bool(open_reviewer_requests(repo)) or not review_running(repo)

    if not script_utils.wait_for(next_step, WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    pending = open_reviewer_requests(repo)
    if pending:
        print("\n".join(reviewer_dispatch_lines(pending)))
        return 0

    review_output = phase_dir(repo) / REVIEW_OUTPUT
    print(review_output.read_text() if review_output.exists() else "No review output was written.")
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "agent":
        return wait_agent(argv[2])
    if len(argv) == 5 and argv[1] == "agent" and argv[3] == "--report-file":
        return wait_agent(argv[2], argv[4])
    if len(argv) == 2 and argv[1] == "review":
        return wait_review(pathlib.Path.cwd().resolve())
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
