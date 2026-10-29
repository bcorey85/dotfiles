---
type: "Change"
change_type: "fixed"
title: "Review loop cannot hand back while its background reviewer runs"
description: "The handback hook denies a review-loop hand-back while the loop's own transcript shows a background agent or shell that has not reported back, so the loop waits and its stop routes to wait-for-loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T06:00:00-05:00"}
seq: 153
kind: "fix"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_loop_that_hands_back_before_its_background_reviewer_reports_gets_wait_for_loop"
asked: "2026-10-28: agent-evals-64 assigned queue item review-loop-hands-back-before-its-own-code"
proof: []
unmeasured: ""
---

## Change

- `handback.open_work_reason`: reads the loop's transcript through `review_loop_gate.LoopTranscript.open_dispatches()`.
  When a dispatch or shell it started has not reported back, the hook denies the hand-back and names the count.
  It runs first in the gate chain, for every status. An unreadable transcript never blocks.
- The loop then ends its turn; the stop gate records the open count and `review_fix.py` routes it to `wait-for-loop`.

## Evidence

- The seq 147 change did not cover it: `unchecked_code_reason` dropped the open-dispatch count, so once a full check
  had run, a hand-back with a background code-reviewer still running was accepted.
- The new test_handback.py and test_review_fix_script.py tests fail on the old script.

## Result

- A review loop hands back only after every reviewer it started has reported.

## Watch

—

## Back-out

Revert the commit.
