"""handback_hook.py: the PreToolUse hook of the review-loop hand-back (`handback.py hook dispatch|handback`), and the
reads of the per-session store that only it uses. handback.py owns the packet; this module records dispatches and
hand-backs and denies a hand-back whose gates fail."""
import json
import os
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import loop_transcript
import script_utils
from capped_review import effective_status
from handback import (
    CLEAN_STATUSES,
    REVIEW_LOOP,
    PacketError,
    load,
)
from handback_store import latest, record, session_rows, was_recorded

RESOLVED_PLAN_IMPACT = re.compile(r"(?im)^[ \t>*`-]*plan_impact:[ \t]*RESOLVED\b")
REPO_LINE = re.compile(r"(?m)^[ \t]*repo:[ \t]*(\S[^\n]*?)[ \t]*$")
ABSOLUTE_PATH = re.compile(r"(?<![\w.~-])/[^\s`'\"<>|;:,()]+")
GIT_TIMEOUT_SECONDS = 10


def loop_steps(session_id, agent_id):
    """The review-loop agent `agent_id`'s coder and reviewer dispatches, in order. Coders resumed with SendMessage are
    not counted: the hook sees only the recipient's id, not its type."""
    return [row["step"] for row in session_rows(session_id, "step", agent_id)]


def claim_no_review(session_id, agent_id):
    """True when `agent_id` is exempt from the reviewer rule: it was exempted before, or the session holds more
    no-review dispatches than exemptions, and this claims one. A dispatch row has no agent id, so a normal loop that
    skips review while an unclaimed no-review loop runs in parallel can take that exemption."""
    stored_rows = session_rows(session_id)
    exempted = [row for row in stored_rows if row.get("kind") == "no-review-exempt"]
    if any(row.get("agent_id") == agent_id for row in exempted):
        return True
    no_review_dispatches = [row for row in stored_rows if row.get("kind") == "dispatch" and row.get("no_review")]
    if len(no_review_dispatches) <= len(exempted):
        return False
    record(session_id, "no-review-exempt", agent_id=agent_id)
    return True



ALREADY_DELIVERED_REASON = ("Your report was already delivered; a second hand-back cannot reach the caller. Use "
                            "SendMessage for anything further, then stop.")
OPEN_WORK_REASON = ("{count} agent(s) or shell(s) you started in the background have not reported back. Do not hand "
                    "back yet: end your turn and wait for each task notification, act on what it reports, then hand "
                    "back.")
UNCHECKED_KIND = "unchecked-code"
LEDGER_KIND = "ledger"


def open_work_reason(open_dispatches):
    """OPEN_WORK_REASON when the count of background dispatches or shells that have not reported back is above zero,
    else None."""
    if not open_dispatches:
        return None
    return OPEN_WORK_REASON.format(count=open_dispatches)


def full_suite_in_ci(transcript, cwd):
    """True when the repo the loop reviewed (else the repo holding cwd, the process cwd when empty) leaves its full
    suite to CI."""
    import full_check

    repo = script_utils.repo_root(transcript.reviewed_root() or cwd or os.getcwd())
    return repo is not None and full_check.full_suite_runs_in_ci(repo)


def last_unchecked_step(session_id, agent_id):
    """The last code step the hook saw when it denied agent_id for an unchecked change, or None."""
    steps = [row.get("last_code_step", 0) for row in session_rows(session_id, UNCHECKED_KIND, agent_id)]
    return max(steps, default=None)


def unchecked_code_reason(ungated, last_step, session_id, agent_id):
    """The deny reason when `ungated` says the loop's transcript shows no passed full_check.py result after its last
    code change (`last_step` is the line of that change), else None.
    The denial is recorded with the last code step it saw and repeats only after a later code change, so a loop that
    hands back again on the same state passes."""
    if not ungated:
        return None
    denied_at = last_unchecked_step(session_id, agent_id)
    if denied_at is not None and last_step <= denied_at:
        return None
    record(session_id, UNCHECKED_KIND, agent_id=agent_id, last_code_step=last_step)
    return loop_transcript.GATE_REASON


def hand_back_plan_edit_reason(transcript, packet):
    """loop_transcript.PLAN_EDIT_REASON when the packet, of any status but plan-impact, has a files_touched that
    names the plan file of the loop's dispatch prompt, else None."""
    if packet is None or packet["status"] == "plan-impact":
        return None

    return loop_transcript.plan_edit_reason(transcript, packet)


def last_ledger_calls(session_id, agent_id):
    """The count of logger calls the loop had made when the hook last denied agent_id for a ledger gap, or None."""
    counts = [row.get("ledger_calls", 0) for row in session_rows(session_id, LEDGER_KIND, agent_id)]
    return max(counts, default=None)


def hand_back_ledger_reason(transcript, packet, session_id, agent_id):
    """The first loop_transcript.packet_ledger_reasons entry when the packet owes finding rows or a metrics line the
    loop did not log, else None. A packet that does not parse owes nothing: the parse gate answers for it.
    The denial is recorded with the count of logger calls the loop had made, refused ones included, and repeats only
    after a later logger call, so a loop whose logger fails and hands back again on the same state passes."""
    if packet is None:
        return None
    reasons = loop_transcript.packet_ledger_reasons(transcript, packet)
    if not reasons:
        return None
    attempted = transcript.ledger_calls_attempted
    denied_at = last_ledger_calls(session_id, agent_id)
    if denied_at is not None and attempted <= denied_at:
        return None
    record(session_id, LEDGER_KIND, agent_id=agent_id, ledger_calls=attempted)
    return reasons[0]


def packet_gate_reason(transcript, packet, session_id, agent_id):
    """The deny reason of the first gate that reads the packet against the transcript: a plan file in files_touched,
    then a ledger gap."""
    return (hand_back_plan_edit_reason(transcript, packet)
            or hand_back_ledger_reason(transcript, packet, session_id, agent_id))


def transcript_gate_reason(event, session_id, agent_id, message, packet):
    """The deny reason of the first gate that reads the loop's own transcript, in order: a background dispatch or
    shell still open, no passed full check after the last code change, a plan file in the packet's files_touched,
    finding rows or a metrics line the packet owes and the loop did not log (the ledger reason, denied once per state).
    The transcript is read once. One that cannot be read never blocks, and a failed full-check scan skips the
    full-check gate only."""
    try:
        transcript = loop_transcript.LoopTranscript(script_utils.agent_transcript_path(event))
        open_dispatches = transcript.open_dispatches()
    except Exception as error:
        print(f"handback hook: transcript gates skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return None
    open_work = open_work_reason(open_dispatches)
    if open_work:
        return open_work
    try:
        in_ci = full_suite_in_ci(transcript, event.get("cwd"))
        ungated, _open_dispatches = loop_transcript.scan(transcript, message, in_ci)
        last_step = loop_transcript.last_code_step(transcript)
    except Exception as error:
        print(f"handback hook: full-check gate skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return packet_gate_reason(transcript, packet, session_id, agent_id)
    return (unchecked_code_reason(ungated, last_step, session_id, agent_id)
            or packet_gate_reason(transcript, packet, session_id, agent_id))


def handle_dispatch(event, session_id, tool_input):
    """Record a review-loop dispatch, or a coder or reviewer step inside one."""
    subagent_type = str(tool_input.get("subagent_type") or "")
    if event.get("agent_type") == REVIEW_LOOP:
        step = "coder" if script_utils.CODERS.match(subagent_type) else "reviewer"
        if step == "coder" or script_utils.REVIEWERS.match(subagent_type):
            record(session_id, "step", agent_id=event.get("agent_id") or "unknown", step=step)
    elif subagent_type == REVIEW_LOOP:
        prompt = str(tool_input.get("prompt") or "")
        record(session_id, "dispatch", no_review=loop_transcript.NO_REVIEW_MODE.search(prompt) is not None,
               resolved_plan_impact=RESOLVED_PLAN_IMPACT.search(prompt) is not None,
               repo=reviewed_repo(prompt, event.get("cwd")))


def reviewed_repo(prompt, cwd):
    """The top level of the repo a review-loop dispatch reviews, by the rule the loop itself follows: the prompt's
    `repo:` line, read from cwd, else the first absolute path the prompt names, else cwd. None when that lies in no
    work tree."""
    named = REPO_LINE.search(prompt)
    first_path = ABSOLUTE_PATH.search(prompt)
    if named:
        directory = os.path.join(cwd or "", os.path.expanduser(named.group(1)))
    elif first_path:
        directory = script_utils.nearest_existing_folder(first_path.group(0))
    else:
        directory = cwd
    if not directory:
        return None
    top = script_utils.repo_root(directory, timeout=GIT_TIMEOUT_SECONDS)
    return str(top) if top else None


def handle_hook(event, kind):
    """Record a review-loop dispatch or hand-back. Returns a deny reason, else None: ALREADY_DELIVERED_REASON for an
    agent whose report is stored, the parse problems for a bad packet seen the first time from its agent, the
    unreviewed reason for a clean packet with no reviewer run, loop_transcript.GATE_REASON when no passed full_check.py
    result follows the last code change, loop_transcript.PLAN_EDIT_REASON when the packet names the plan file, or the
    ledger reason when the packet owes finding rows or a metrics line (once, until the loop makes another logger
    call)."""
    session_id = event.get("session_id")
    if not session_id:
        return None
    tool_input = event.get("tool_input") or {}
    if kind == "dispatch":
        handle_dispatch(event, session_id, tool_input)
        return None
    if kind != "handback" or event.get("agent_type") != REVIEW_LOOP:
        return None
    message = str(tool_input.get("message", ""))
    agent_id = event.get("agent_id") or "unknown"
    if was_recorded(session_id, agent_id, "handback"):
        return ALREADY_DELIVERED_REASON
    try:
        packet = load(message)
        status, problems = packet["status"], []
    except PacketError as error:
        packet, status, problems = None, "invalid", error.problems
    if problems and not was_recorded(session_id, agent_id, "rejected"):
        record(session_id, "rejected", agent_id=agent_id, problems=problems)
        return ("The review-loop packet does not parse: " + "; ".join(problems) +
                ". Hand back one JSON object alone (no fence, no prose around it) with the keys and rules of the "
                "Return packet section in your instructions.")
    clean_status = status
    if packet is not None:
        dispatch = latest(session_id)["dispatch"] or {}
        clean_status = effective_status(packet, dispatch.get("repo"))
    steps = loop_steps(session_id, agent_id)
    unreviewed = (clean_status in CLEAN_STATUSES and "reviewer" not in steps
                  and not claim_no_review(session_id, agent_id))
    if unreviewed and not was_recorded(session_id, agent_id, "unreviewed"):
        record(session_id, "unreviewed", agent_id=agent_id)
        return ("This review-loop hand-back is clean but no reviewer ran. Dispatch the code-reviewer on the diff, fix "
                "what it finds, then hand back again.")
    gate_reason = transcript_gate_reason(event, session_id, agent_id, message, packet)
    if gate_reason:
        return gate_reason

    unreviewed_fix = (clean_status in CLEAN_STATUSES and "reviewer" in steps
                      and steps[-1:] == ["coder"])
    record(session_id, "handback", agent_id=agent_id, status=status, problems=problems, message=message,
           no_reviewer=unreviewed, unreviewed_fix=unreviewed_fix)
    return None


def command_hook(argv):
    """Never blocks on its own error."""
    try:
        if argv not in (["dispatch"], ["handback"]):
            print(f"handback hook: unknown kind {' '.join(argv)!r}; want dispatch or handback", file=sys.stderr)
            return 0
        reason = handle_hook(json.load(sys.stdin), argv[0])
        if reason:
            script_utils.pre_tool_use_deny(reason)
    except Exception as error:
        print(f"handback hook: {error}", file=sys.stderr)
    return 0

