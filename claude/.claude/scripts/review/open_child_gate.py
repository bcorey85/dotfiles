#!/usr/bin/env python3
"""open_child_gate.py — PreToolUse on SubagentHandback: a goal-blind-researcher hands back only after every
background agent it launched has reported or ended on an API error.

Denies a hand-back while the researcher's own transcript holds a background launch with no task notification whose
agent has not ended on an API error (the count `loop_transcript.LoopTranscript.open_dispatches` keeps), and tells it
to wait for the notice, Glob for the file the child writes, then hand back, and to hand back a failure when the child
failed. The deny is once per agent (kept in the handback store): a later hand-back passes, so a child that never
reports cannot trap it. Every other agent type passes, and so does a hand-back with no open child.

Hook JSON on stdin; a deny decision JSON on stdout; exit 0. Any parse failure passes (fail open) and says why on
stderr: this gate adds a check, it must never stop an agent on its own error. A child launched in the foreground has
no launch notice, so it is never counted.
"""
import json
import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback_store
import loop_transcript
import script_utils

GATED_AGENT = "goal-blind-researcher"
DENIED_KIND = "open_child_denied"

DENY_REASON = (
    "A background agent you launched has not reported back ({count} open). Do not hand back yet: wait for its "
    "completion notice, then Glob for the file it writes and hand back the path. If the child failed, hand back a "
    "failure that says so; never hand back a caveat on a path that may be partial."
)


def deny_reason_for(hook):
    """The deny reason when the hook is a goal-blind-researcher hand-back with a child still open, else None."""
    if hook.get("agent_type") != GATED_AGENT:
        return None
    transcript = loop_transcript.LoopTranscript(script_utils.agent_transcript_path(hook))
    open_children = transcript.open_dispatches()
    if not open_children:
        return None

    # Once per agent: a child that never sends a notice must not trap the hand-back. Without a session id the denial
    # cannot be remembered, so the call passes.
    session_id, agent_id = hook.get("session_id"), hook.get("agent_id") or "unknown"
    if not session_id or handback_store.was_recorded(session_id, agent_id, DENIED_KIND):
        return None

    handback_store.record(session_id, DENIED_KIND, agent_id=agent_id, open_children=open_children)
    return DENY_REASON.format(count=open_children)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    hook = json.load(sys.stdin)
    reason = deny_reason_for(hook)
    if reason:
        script_utils.pre_tool_use_deny(reason)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, visibly
        print(f"open-child-gate: skipped, {type(e).__name__}: {e}", file=sys.stderr)
