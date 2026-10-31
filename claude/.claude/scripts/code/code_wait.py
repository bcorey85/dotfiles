#!/usr/bin/env python3
"""Wait, inside the /code fork, for a background coder or the review loop.

    python3 ~/.claude/scripts/code/code_wait.py agent <agent id>
    python3 ~/.claude/scripts/code/code_wait.py review

Nested Agent calls in a fork return at once, and a fork that ends its turn hands back, so the fork waits here instead.
`agent` waits for the coder's subagent transcript to finish and prints its hand-back report. `review` waits for the
code_review_start.py process that `code_review_start.py --detach` left and prints its output. Each call waits at most
WAIT_SECONDS, under the fork's 600-second Bash timeout, then says to run the same command again.
"""

import json
import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import loop_transcript
import script_utils

PROJECTS = pathlib.Path.home() / ".claude" / "projects"
WAIT_SECONDS = 540
POLL_SECONDS = 5
STILL_WORKING = "Still working. Run the same command again, with the Bash timeout set to 600000."
PHASE_DIR_NAME = "code-phase"
PID_FILE = "pid"
REVIEW_OUTPUT = "review.out"


def agent_transcript(agent_id):
    # The newest transcript of this agent id under any session's subagents folder, or None before it is written.
    transcripts = list(PROJECTS.glob(f"*/*/subagents/{script_utils.subagent_transcript_name(agent_id)}"))
    if not transcripts:
        return None
    return max(transcripts, key=lambda transcript: transcript.stat().st_mtime)


def agent_finished(transcript):
    meta_path = transcript.with_suffix(".meta.json")
    if meta_path.exists() and json.loads(meta_path.read_text()).get("finished"):
        return True

    return loop_transcript.has_delivered_handback(transcript)


def agent_report(transcript):
    # The message of the agent's last hand-back call a hook did not deny, else its last text.
    read = loop_transcript.LoopTranscript(transcript)
    return read.handback_message or read.last_text or "The agent finished with no report."


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


def wait_agent(agent_id):
    def finished():
        transcript = agent_transcript(agent_id)
        return transcript is not None and agent_finished(transcript)

    if not script_utils.wait_for(finished, WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    print(agent_report(agent_transcript(agent_id)))
    return 0


def wait_review(repo):
    if not script_utils.wait_for(lambda: not review_running(repo), WAIT_SECONDS, POLL_SECONDS):
        print(STILL_WORKING)
        return 0

    review_output = phase_dir(repo) / REVIEW_OUTPUT
    print(review_output.read_text() if review_output.exists() else "No review output was written.")
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "agent":
        return wait_agent(argv[2])
    if len(argv) == 2 and argv[1] == "review":
        return wait_review(pathlib.Path.cwd().resolve())
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
