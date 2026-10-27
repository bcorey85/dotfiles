---
type: "Change"
title: "code_step resume routes a late review hand-back on its report"
description: "After a wait-cap stop, `resume` routes a review-loop report that arrived late on that report, and the stale \"never handed back\" question is replaced."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T23:05:53-05:00"}
seq: 84
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_review_loop_that_hands_back_after_the_wait_cap_is_routed_on_its_report"
asked: ""
proof: []
unmeasured: "Wait-cap stops are not counted by outcome; no intake number reads them."
---

## Change

`review_answer_sent` also counts a hand-back that `awaited_handback` finds, so `resume` goes to `after-review` instead of the
review-cap ask. `clear_question` already runs before each verb, so the stale question goes. The 1710 s cap is unchanged:
nothing in the code holds a review-loop's real length.

## Evidence

A review-loop ran two rounds past the cap; its report arrived after the stop, and the next `resume` asked the user while
question.md still said the review never handed back.

## Result

A late report is routed on what it says.

## Watch

None.

## Back-out

Revert the commit.
