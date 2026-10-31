---
type: "Change"
change_type: "fixed"
title: "A review-loop waiting on its own background agent is not a missing hand-back"
description: "review_loop_gate.py records each review-loop stop with its count of open background agents; review_fix.py packet prints wait-for-loop, not stop-no-handback, while the loop waits, so /review and /fix no longer re-dispatch a second loop onto files the first loop's coder still edits."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T20:00:13-05:00"}
seq: 68
kind: "fix"
components: ["script/review-loop-gate", "script/handback", "script/review-fix", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_loop_waiting_on_a_background_agent_gets_wait_for_loop_and_no_miss"
asked: ""
proof: []
unmeasured: ""
---

## Change

- Every review-loop SubagentStop appends a stop row to the hand-back store with the loop's count of open background
  agents: a launch with no notification back, or a SendMessage resume with no later report. A resume is matched by its
  full `resumedAgentId` and closed by a later message from that agent or a notification under the SendMessage's own
  tool_use_id, which is how the harness reports a resumed agent. A transcript that cannot be
  read writes a 0 row, so an old wait always clears.
- `hand_back_gap` returns a new gap, loop-waiting, when no hand-back is current and the latest stop after the latest
  dispatch has an open agent. The commit gate and the /code boundary refuse clean during the wait.
- `review_fix.py packet` prints `ACTION: wait-for-loop` (exit 3) on that gap and counts no miss. A second `packet` on
  the same stop prints `ACTION: stop` naming the time the wait began, and says not to re-dispatch. A new stop waits
  again.
- /review and /fix list the new action: end the turn, run the packet step again when the loop's completion notice
  arrives, never re-dispatch.

## Evidence

- A /fix run's review-loop launched its coder in the background and stopped. `packet` printed stop-no-handback, whose
  advice re-dispatches the loop, which would have started a second coder on the files the first coder still edited.
- The new tests fail on the base commit and pass after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
