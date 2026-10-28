---
type: "Change"
title: "A review blocker stop records its reason so resume and review-again agree"
description: "A /code run stopped by a review blocker now records a stop reason; resume routes it to a re-review of the same diff and review-again accepts it, so the two verbs no longer point at each other."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T00:23:28-05:00"}
seq: 161
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_review_blocker_stop_records_its_reason_and_resume_and_review_again_do_not_point_at_each_other"
asked: ""
proof: []
unmeasured: "The loop between the two verbs is not counted in any intake log, so no intake number reads it."
---

## Change

- The stop reason `review-blocker` is recorded for three stops: a critical blocker with no asks, a setup-fault stop (it shares the blocker stop text), and a second critical blocker with asks in the same phase.
- `resume` at that stop tells the user to run `review-again` (or restart), instead of asking for status.
- `review-again` accepts a run stopped on that reason.

## Evidence

- Read of the stop routes: the blocker stop recorded no reason, so `resume` fell to the unrecorded-state question,
  which named a verb that refused the run in turn.
- The test fails before the change (no recorded reason, and `review-again` refused the run) and passes after. The
  older test for a stop with no recorded reason now clears the reason first.

## Result

- Resume and review-again agree on a blocker stop, and neither sends the user to the other.

## Watch

No watch: nothing in the intake logs counts verb loops at a blocker stop.

## Back-out

Revert the new stop reason, its resume handler and the extra reason in the `review-again` guard.
