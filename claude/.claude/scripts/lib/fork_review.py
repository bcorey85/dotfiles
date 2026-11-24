"""fork_review.py: whether a /code fork that dispatched a coder for a phase also ran its review of that phase.

The fork's own transcript decides. The reader never reads the run folder: a review packet or a stop.md left there by an
earlier run says nothing about this run. The transcript is split into phase segments at each phase_start.py call that
follows a segment needing no review or already reviewed (a transcript with no such call is one segment). A segment
that holds a coder dispatch needs, after its first coder dispatch, a code_review_start.py call followed by a
code_wait.py review call, or a stop.md write. A tick coder dispatched after the converged review comes after the
first coder dispatch, so it needs no second review.

Fails open: a transcript that is missing, cannot be read, or belongs to another agent type is never judged, and a torn
line is skipped. Two callers, each of which checks its own event name:
- gates/staged_claim_gate.py, on SubagentStop (the final text reply of a fork);
- code/coder_gate.py `hook`, on PreToolUse SubagentHandback (a fork that ends through the hand-back).

Fields each event supplies: PreToolUse SubagentHandback `agent_type` and `agent_transcript_path` are `exercised`
(test_open_child_gate.py, test_coder_gate.py). The SubagentStop field names come from no captured event; when the event
lacks `agent_type` the agent's meta file (`agentType`) names it, and when it lacks `agent_transcript_path` the path is
read from the session transcript and the agent id."""
import json
import os
import pathlib
import re
import sys
from collections import namedtuple

import loop_transcript
import script_utils
from code_run_names import PHASE_START_SCRIPT, REVIEW_START_SCRIPT, WAIT_REVIEW_VERB, WAIT_SCRIPT
from shell_command_words import script_call_arguments, unquoted_word
from shell_expansion import redirect_target_words
from shell_statements import shell_code
from stop_file_names import STOP_FILE

# The first record of a /code fork is the skill text, which opens with the skill's base directory.
SKILL_BASE = re.compile(r"\ABase directory for this skill: \S*/skills/code\s*\n")

CODE_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "code"

REASON = ("This /code run dispatched a coder for a phase but ran no review of it and wrote no stop. Run step 5 of the "
          "/code skill now: write the handoff block to `<run folder>/handoff.txt`, run `python3 "
          f"{CODE_SCRIPTS_DIR / REVIEW_START_SCRIPT} <lane> - 1 <run folder>/handoff.txt --base <phase base> "
          "--detach` (the plan path and phase number in place of `- 1` when the run has a plan), then `python3 "
          f"{CODE_SCRIPTS_DIR / WAIT_SCRIPT} {WAIT_REVIEW_VERB}`. If the run must stop before its review, write the "
          "stop to `<run folder>/stop.md` first.")

# One phase of the run. Each field except coder_line holds transcript line numbers, oldest first. coder_line is the
# line of the first coder dispatch, None when the phase dispatched none.
# collections.namedtuple, not typing.NamedTuple: the coder gate imports this module on every Bash call.
Segment = namedtuple("Segment", ["coder_line", "review_start_lines", "review_wait_lines", "stop_lines"])
ForkReview = namedtuple("ForkReview", ["is_code_run", "segments"])


def new_segment():
    return Segment(None, [], [], [])


def record_of(line):
    """The JSON object of one transcript line, None for a torn line or any other shape."""
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    return record


def string_content(record):
    """The message content of a record when it is one string, else an empty string."""
    message = record.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    return content


def writes_stop_file(command):
    """Whether a Bash output redirect of the command has a target whose basename is the stop file."""
    for target_word in redirect_target_words(shell_code(command)):
        if os.path.basename(unquoted_word(target_word)) == STOP_FILE:
            return True
    return False


def read_bash_call(segments, line_number, command):
    if not isinstance(command, str):
        return

    # A phase_start.py call opens a new phase only after a phase that needs no review or got one: a fork also calls it
    # mid-phase to read the run state, and a resumed fork's tick coder comes before its first call.
    if script_call_arguments(command, PHASE_START_SCRIPT) and segment_reviewed(segments[-1]):
        segments.append(new_segment())
    segment = segments[-1]
    if writes_stop_file(command):
        segment.stop_lines.append(line_number)
    if script_call_arguments(command, REVIEW_START_SCRIPT):
        segment.review_start_lines.append(line_number)

    wait_calls = script_call_arguments(command, WAIT_SCRIPT)
    if any(call[:1] == [WAIT_REVIEW_VERB] for call in wait_calls):
        segment.review_wait_lines.append(line_number)


def read_agent_call(segments, line_number, tool_input):
    segment = segments[-1]
    if segment.coder_line is not None:
        return

    subagent_type = tool_input.get("subagent_type")
    if not isinstance(subagent_type, str) or not script_utils.CODERS.match(subagent_type):
        return
    segments[-1] = segment._replace(coder_line=line_number)


def read_line(segments, line_number, line):
    for name, tool_input in script_utils.tool_use_calls(line):
        if name == "Bash":
            read_bash_call(segments, line_number, tool_input.get("command"))
        elif name == "Agent":
            read_agent_call(segments, line_number, tool_input)

    for written_path in loop_transcript.call_paths(line):
        if os.path.basename(written_path) == STOP_FILE:
            segments[-1].stop_lines.append(line_number)


def read_fork_review(transcript_path):
    """The ForkReview of a fork transcript, read in one pass. A transcript whose first record is not the /code skill
    text is not a code run and is not read further."""
    segments = [new_segment()]
    seen_first_record = False
    with open(transcript_path, encoding="utf-8", errors="replace") as transcript:
        for line_number, line in enumerate(transcript):
            if seen_first_record:
                read_line(segments, line_number, line)
                continue

            record = record_of(line)
            if record is None:
                continue
            seen_first_record = True
            if not SKILL_BASE.match(string_content(record)):
                return ForkReview(False, segments)
    return ForkReview(seen_first_record, segments)


def segment_reviewed(segment):
    """Whether a phase needs no review or got one: it dispatched no coder, or a stop.md write comes after the first
    coder dispatch, or a code_review_start.py call comes after it and a code_wait.py review call at or after that."""
    coder_line = segment.coder_line
    if coder_line is None:
        return True
    if any(stop_line > coder_line for stop_line in segment.stop_lines):
        return True

    for start_line in segment.review_start_lines:
        if start_line <= coder_line:
            continue
        if any(wait_line >= start_line for wait_line in segment.review_wait_lines):
            return True
    return False


def reviewed(fork_review):
    """Whether every phase of the fork is reviewed."""
    return all(segment_reviewed(segment) for segment in fork_review.segments)


def transcript_path_of(hook):
    """The fork's transcript path from the event, None when the event names no way to find it."""
    names_agent_path = hook.get("agent_transcript_path")
    names_session_path = hook.get("transcript_path") and hook.get("agent_id")
    if not names_agent_path and not names_session_path:
        return None
    return script_utils.agent_transcript_path(hook)


def missing_review_reason(hook):
    """REASON when the hook's agent is a /code fork that dispatched a coder for a phase and ran no review of it and
    wrote no stop, else None. It does not check the event name."""
    transcript_path = transcript_path_of(hook)
    if transcript_path is None or not os.path.isfile(transcript_path):
        return None

    agent_type = hook.get("agent_type") or loop_transcript.agent_meta(transcript_path).get("agentType")
    if agent_type != script_utils.FORK_AGENT_TYPE:
        return None

    try:
        fork_review = read_fork_review(transcript_path)
    except OSError as error:
        print(f"fork-review: cannot read {transcript_path}: {error}", file=sys.stderr)
        return None
    if not fork_review.is_code_run or reviewed(fork_review):
        return None
    return REASON
