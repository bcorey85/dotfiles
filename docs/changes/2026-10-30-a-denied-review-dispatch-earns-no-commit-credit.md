---
type: "Change"
change_type: "fixed"
title: "A denied review dispatch earns no commit credit"
description: "A review-loop dispatch row counts only once a PostToolUse row shows its call ran, so a dispatch another hook denied no longer makes a good hand-back stale."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T01:05:05-05:00"}
seq: 308
kind: "fix"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::HookTest::test_a_denied_re_dispatch_leaves_the_good_hand_back_current"
asked: ""
proof: []
unmeasured: "No intake number counts denied dispatches; the defect was found by a code trace."
---

## Change

`handback.py hook dispatch` writes the review-loop dispatch row at PreToolUse with the call's `tool_use_id`. The new
`handback.py hook ran`, a PostToolUse hook on Agent, writes a `dispatch-ran` row for the same call. `handback_store`
counts a dispatch row that names its call only once a `dispatch-ran` row names it too; a row with no call id (a
script wrote it) counts as before. `latest()` clears the stop row on every dispatch row, run or not, so a foreground
loop never reads an earlier loop's stop as its own. Hand-back rows count as written: no sibling hook denies a
review-loop hand-back, and `handback.py`'s own deny stores nothing.

Needs a `PostToolUse` entry in `claude/.claude/settings.json` (matcher `Agent`, command
`sh ~/.claude/scripts/tools/hook-python ~/.claude/scripts/review/handback.py hook ran`). Without it no dispatch made
by the hook counts, and commit credit stops.

## Evidence

A code trace: the dispatch hook writes before sibling hooks can deny, and no hook event fires after a deny.

## Result

A denied re-dispatch leaves `latest()`'s dispatch, hand-back and unanswered count unchanged. A foreground dispatch's
hand-back is accepted before its call is proven, and the dispatch counts once the `ran` row lands.

## Watch

None; no intake number counts denied dispatches.

## Back-out

Revert the commit and remove the settings entry.
