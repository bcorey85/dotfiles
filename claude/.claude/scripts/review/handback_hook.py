"""handback_hook.py: the hooks of the review-loop hand-back (`handback.py hook dispatch|handback|ran`), and the
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
from handback_store import DISPATCH_RAN, hand_back_dispatch_rows, record, session_rows, was_recorded

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
    no_review_dispatches = [row for row in hand_back_dispatch_rows(session_id) if row.get("no_review")]
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
DEAD_REVIEWER_KIND = "dead-reviewer"
DEAD_REVIEWER_REASON = ("The latest dispatch of one reviewer kind ended on an API error, so the loop holds no finished "
                        "review from that run. Dispatch the reviewer again on the diff, fix what it "
                        "finds, then hand back again. If the reviewer cannot be run again, hand back again; that "
                        "hand-back is recorded as not reviewed and gets no clean credit.")


def open_work_reason(open_dispatches):
    """OPEN_WORK_REASON when the count of background dispatches or shells that have not reported back is above zero,
    else None."""
    if not open_dispatches:
        return None
    return OPEN_WORK_REASON.format(count=open_dispatches)


def last_unchecked_step(session_id, agent_id):
    """The last code step the hook saw when it denied agent_id for an unchecked change, or None."""
    steps = [row.get("last_code_step", 0) for row in session_rows(session_id, UNCHECKED_KIND, agent_id)]
    return max(steps, default=None)


def unchecked_code_reason(ungated, last_step, session_id, agent_id):
    """`ungated`, the deny reason from loop_transcript.scan when no valid full-check receipt exists for the tree the
    loop reviewed, else None (`ungated` is None). `last_step` is the transcript line of the loop's last code change.
    The denial is recorded with the last code step it saw and repeats only after a later code change, so a loop that
    hands back again on the same state passes."""
    if not ungated:
        return None
    denied_at = last_unchecked_step(session_id, agent_id)
    if denied_at is not None and last_step <= denied_at:
        return None
    record(session_id, UNCHECKED_KIND, agent_id=agent_id, last_code_step=last_step)
    return ungated


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


def denied_dead_reviewers(session_id, agent_id):
    """The agent ids of dead reviewer dispatches the hook already denied agent_id for."""
    return {dead for row in session_rows(session_id, DEAD_REVIEWER_KIND, agent_id) for dead in row.get("reviewers", [])}


def dead_reviewer_reason(dead_reviewers, session_id, agent_id):
    """DEAD_REVIEWER_REASON when a dead reviewer dispatch in `dead_reviewers` has not been denied for this loop, else
    None. The denial is recorded with the dead agent ids and repeats only for a new dead dispatch, so a loop whose
    reviewer cannot run again hands back again and passes."""
    denied = denied_dead_reviewers(session_id, agent_id)
    if set(dead_reviewers) <= denied:
        return None
    record(session_id, DEAD_REVIEWER_KIND, agent_id=agent_id, reviewers=list(dead_reviewers))
    return DEAD_REVIEWER_REASON


def packet_gate_reason(transcript, packet, session_id, agent_id):
    """The deny reason of the first gate that reads the packet against the transcript: a plan file in files_touched,
    then a ledger gap."""
    return (hand_back_plan_edit_reason(transcript, packet)
            or hand_back_ledger_reason(transcript, packet, session_id, agent_id))


def transcript_gates(event, session_id, agent_id, message, packet, clean_status):
    """`(reason, reviewer_dead)`. `reason` is the deny reason of the first gate that reads the loop's own transcript,
    in order: a background dispatch or shell still open, a clean hand-back (`clean_status`) whose latest dispatch of
    one reviewer kind ended on an API error (denied once per dead dispatch), no valid full-check receipt for the
    tree, a plan file in the packet's files_touched, finding rows or a metrics line the packet owes and the loop did
    not log (the ledger reason, denied once per state). `reviewer_dead` is True for a clean hand-back whose latest
    dispatch of some reviewer kind died, denied or not: the hand-back that passes is stored as not reviewed.
    The transcript is read once. One that cannot be read never blocks and reports no dead reviewer, and a failed
    full-check scan skips the full-check gate only."""
    try:
        transcript = loop_transcript.LoopTranscript(script_utils.agent_transcript_path(event))
        open_dispatches = transcript.open_dispatches()
    except Exception as error:
        print(f"handback hook: transcript gates skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return None, False
    open_work = open_work_reason(open_dispatches)
    if open_work:
        return open_work, False
    dead_reviewers = transcript.dead_reviewers() if clean_status in CLEAN_STATUSES else []
    reviewer_dead = bool(dead_reviewers)
    if reviewer_dead:
        dead_reason = dead_reviewer_reason(dead_reviewers, session_id, agent_id)
        if dead_reason:
            return dead_reason, True
    try:
        ungated, _open_dispatches = loop_transcript.scan(transcript, message, event.get("cwd"))
        last_step = loop_transcript.last_code_step(transcript)
    except Exception as error:
        print(f"handback hook: full-check gate skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return packet_gate_reason(transcript, packet, session_id, agent_id), reviewer_dead
    reason = (unchecked_code_reason(ungated, last_step, session_id, agent_id)
              or packet_gate_reason(transcript, packet, session_id, agent_id))
    return reason, reviewer_dead


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
               repo=reviewed_repo(prompt, event.get("cwd")), tool_use_id=event.get("tool_use_id"))


def handle_dispatch_ran(event, session_id):
    """PostToolUse on Agent: the call ran, so the dispatch row it named at PreToolUse now counts. Only a review-loop
    dispatch from outside the loop has such a row."""
    tool_use_id = event.get("tool_use_id")
    is_loop_dispatch = (event.get("tool_input") or {}).get("subagent_type") == REVIEW_LOOP
    if tool_use_id and is_loop_dispatch and event.get("agent_type") != REVIEW_LOOP:
        record(session_id, DISPATCH_RAN, tool_use_id=tool_use_id)


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


def record_script_dispatch(session_id, repo_dir):
    """The dispatch row the Agent hook writes for a review-loop, for a loop that runs as a script instead."""
    record(session_id, "dispatch", no_review=False, repo=reviewed_repo("", str(repo_dir)))


def handle_hook(event, kind):
    """Record a review-loop dispatch or hand-back, or for kind `ran` the dispatch-ran row of a dispatch whose call ran.
    Returns a deny reason, else None: ALREADY_DELIVERED_REASON for an
    agent whose report is stored, the parse problems for a bad packet seen the first time from its agent, the
    unreviewed reason for a clean packet with no reviewer run, DEAD_REVIEWER_REASON (once per dead dispatch) for a
    clean packet whose latest dispatch of one reviewer kind ended on an API error, loop_transcript.GATE_REASON when
    no valid full-check receipt exists for the tree the loop reviewed, loop_transcript.PLAN_EDIT_REASON when the
    packet names the plan file, or the ledger reason when the packet owes finding rows or a metrics line (once,
    until the loop makes another logger call). A clean packet that passes while its latest reviewer dispatch is
    dead is stored with no_reviewer set, so it earns no clean credit."""
    session_id = event.get("session_id")
    if not session_id:
        return None
    tool_input = event.get("tool_input") or {}
    if kind == "dispatch":
        handle_dispatch(event, session_id, tool_input)
        return None
    if kind == "ran":
        handle_dispatch_ran(event, session_id)
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
        dispatch_rows = hand_back_dispatch_rows(session_id)
        dispatch = dispatch_rows[-1] if dispatch_rows else {}
        clean_status = effective_status(packet, dispatch.get("repo"))
    steps = loop_steps(session_id, agent_id)
    unreviewed = (clean_status in CLEAN_STATUSES and "reviewer" not in steps
                  and not claim_no_review(session_id, agent_id))
    if unreviewed and not was_recorded(session_id, agent_id, "unreviewed"):
        record(session_id, "unreviewed", agent_id=agent_id)
        return ("This review-loop hand-back is clean but no reviewer ran. Dispatch the code-reviewer on the diff, fix "
                "what it finds, then hand back again.")
    gate_reason, reviewer_dead = transcript_gates(event, session_id, agent_id, message, packet, clean_status)
    if gate_reason:
        return gate_reason

    unreviewed_fix = (clean_status in CLEAN_STATUSES and "reviewer" in steps
                      and steps[-1:] == ["coder"])
    record(session_id, "handback", agent_id=agent_id, status=status, problems=problems, message=message,
           no_reviewer=unreviewed or reviewer_dead, unreviewed_fix=unreviewed_fix)
    return None


def command_hook(argv):
    """Never blocks on its own error."""
    try:
        if argv not in (["dispatch"], ["handback"], ["ran"]):
            print(f"handback hook: unknown kind {' '.join(argv)!r}; want dispatch, handback or ran", file=sys.stderr)
            return 0
        reason = handle_hook(json.load(sys.stdin), argv[0])
        if reason:
            script_utils.pre_tool_use_deny(reason)
    except Exception as error:
        print(f"handback hook: {error}", file=sys.stderr)
    return 0

