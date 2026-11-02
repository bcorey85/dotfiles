#!/usr/bin/env python3
"""open_child_gate.py — PreToolUse on SubagentHandback: a goal-blind-researcher or a /code fork hands back only after
the background agents it launched have reported or ended.

goal-blind-researcher: denies a hand-back while the researcher's own transcript holds a background launch with no
task notification whose agent has not ended on an API error (the count `loop_transcript.LoopTranscript.open_dispatches`
keeps), and tells it to wait for the notice, Glob for the file the child writes, then hand back, and to hand back a
failure when the child failed. The deny is once per agent.

code-fork: denies a hand-back while a background launch has not reported back and its agent's own transcript does
not show it finished or dead (`loop_transcript.agent_finished`, the test code_wait.py waits on), and tells the fork to
stay active and wait with code_wait.py. The deny is once per child agent.

Each deny is kept in the handback store, so a child that never reports cannot trap its caller: a later hand-back
passes. Every other agent type passes, and so does a hand-back with no open child.

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

RESEARCHER = "goal-blind-researcher"
CODE_FORK = "code-fork"
DENIED_KIND = "open_child_denied"

RESEARCHER_DENY_REASON = (
    "A background agent you launched has not reported back ({count} open). Do not hand back yet: wait for its "
    "completion notice, then Glob for the file it writes and hand back the path. If the child failed, hand back a "
    "failure that says so; never hand back a caveat on a path that may be partial."
)
CODE_FORK_DENY_REASON = (
    "An agent you dispatched is still running ({children}). Do not hand back and do not end your turn: you stay "
    "active. Run `python3 ~/.claude/scripts/code/code_wait.py agent <agentId>` with the Bash timeout set to 600000, "
    "again while it prints `Still working`, then go on with the step that waits on its report."
)


def researcher_deny_reason(hook, transcript):
    open_children = transcript.open_dispatches()
    if not open_children:
        return None

    # Once per agent: a child that never sends a notice must not trap the hand-back. Without a session id the denial
    # cannot be remembered, so the call passes.
    session_id, agent_id = hook.get("session_id"), hook.get("agent_id") or "unknown"
    if not session_id or handback_store.was_recorded(session_id, agent_id, DENIED_KIND):
        return None

    handback_store.record(session_id, DENIED_KIND, agent_id=agent_id, open_children=open_children)
    return RESEARCHER_DENY_REASON.format(count=open_children)


def live_children(transcript):
    """The ids of the background launches that have not reported back and whose agent's own transcript does not show
    it finished or dead: the agent id, or the launch's tool_use_id when its result names none."""
    children = []
    for launch_id in transcript.open_launches():
        agent_id = transcript.launched_agent(launch_id)
        if not agent_id:
            children.append(launch_id)
            continue
        child_transcript = script_utils.sibling_transcript_path(transcript.path, agent_id)
        if not loop_transcript.agent_finished(child_transcript):
            children.append(agent_id)
    return children


def code_fork_deny_reason(hook, transcript):
    children = live_children(transcript)
    if not children:
        return None

    # Once per child: a child that never ends must not trap the fork. Without a session id the denial cannot be
    # remembered, so the call passes.
    session_id, agent_id = hook.get("session_id"), hook.get("agent_id") or "unknown"
    if not session_id:
        return None
    denied_rows = handback_store.session_rows(session_id, DENIED_KIND, agent_id)
    denied = {child for row in denied_rows for child in row.get("children", [])}
    undenied = [child for child in children if child not in denied]
    if not undenied:
        return None

    handback_store.record(session_id, DENIED_KIND, agent_id=agent_id, children=undenied)
    return CODE_FORK_DENY_REASON.format(children=", ".join(children))


GATED_AGENTS = {RESEARCHER: researcher_deny_reason, CODE_FORK: code_fork_deny_reason}


def deny_reason_for(hook):
    """The deny reason when the hook is a gated agent's hand-back with a child still open, else None."""
    deny_reason = GATED_AGENTS.get(hook.get("agent_type"))
    if deny_reason is None:
        return None
    transcript = loop_transcript.LoopTranscript(script_utils.agent_transcript_path(hook))
    return deny_reason(hook, transcript)


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
