---
type: "Change"
change_type: "fixed"
title: "A false-clean stop names review-again, and review-again recovers it in place"
description: "When the hand-back record refuses the clean mark, code_step saves the run as stopped with reason false-clean and tells the session to invoke Skill code with `review-again`, which now accepts that stop and runs one more review on the same diff."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:00:00-05:00"}
seq: 131
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_review_again_recovers_a_false_clean_stop_in_place"
asked: "2026-10-27: agent-evals-64 assigned the second done-when of queue item review-loop-hands-back-converged-with-fixes-after (rank 196)"
proof: []
unmeasured: ""
---

## Change

- `code_step_boundary.mark_review_gate_clean`: a `false_clean_reason` stop saves `stage=stopped`,
  `stopReason=false-clean`, and its text says to invoke Skill code with `review-again`, in place of "Tell the user".
- `code_step_review.STAGE_GUARDS`: `review-again` accepts the `false-clean` stop.

## Evidence

- A /code run stopped on a false-clean hand-back. `review-again` refused it, `resume` pointed only at
  `start --restart`, and neither stop named `review-again`. The only exits were a full phase rerun or `tick`.
- The new test fails on the old scripts: the stop names no verb and saves no stop reason.

## Result

- A false-clean stop recovers with one more review over the current diff, with no phase restart.

## Watch

—

## Back-out

Revert the commit.
