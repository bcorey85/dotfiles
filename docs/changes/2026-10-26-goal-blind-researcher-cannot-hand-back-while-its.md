---
type: "Change"
title: "goal-blind researcher cannot hand back while its child still runs"
description: "A new PreToolUse hook on SubagentHandback denies goal-blind-researcher's first hand-back while a child it dispatched is still open, once per agent, and fails open."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:53:23-05:00"}
seq: 86
kind: "fix"
components: ["agent/goal-blind-researcher"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_open_child_gate.py::OpenChildGateTest::test_hand_back_with_open_background_child_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/review/open_child_gate.py`. It reads the agent's transcript with the review-loop gate's dispatch
  reader. When goal-blind-researcher hands back while a child it dispatched has not returned, it denies the hand-back
  once and names the open child. A second hand-back from the same agent passes. Any read error passes.
- `handback.was_recorded(session_id, agent_id, kind)` is the shared once-per-agent record; `was_rejected` and
  `was_unreviewed` are replaced by it.

## Evidence

- goal-blind-researcher handed back its paths while its spec-research child had not reported, with a caveat that the
  research file might be partial. The file was complete, but the main session had to inspect it before designing on
  it.
- Eight new tests; the deny test fails on the base tree.

## Result

- Not live until the hook is registered. The settings write was blocked by the project-settings hook, so the user
  adds `{"type": "command", "command": "python3 ~/.claude/scripts/review/open_child_gate.py"}` to the PreToolUse
  `SubagentHandback` hooks, after the `handback.py hook handback` entry.

## Watch

—

## Back-out

Revert the commit and remove the settings entry.
