---
type: "Change"
change_type: "fixed"
title: "Review packet says when the commit gate does not credit a clean review"
description: "The review packet step prints a COMMIT CREDIT line with the reason when a converged or deferred review earned no commit credit, so the session learns it before review-commit-gate denies the commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T02:50:45-06:00"}
seq: 8
kind: "fix"
components: ["skill/review", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_clean_loop_the_commit_gate_does_not_credit_says_why"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_fix.py` `packet`, on a clean packet, asks `handback.false_clean_reason` for the session and prints `COMMIT CREDIT: the commit gate does not credit this review yet: <reason>.` when it refuses. A credited review prints nothing new.

## Evidence

judgment: the loop records commit credit in `review_loop_packet.write_handback_rows` and drops `record_clean_review`'s refusal reason. A session then met the refusal only as a denied commit. The loop's stderr goes to its log, not to the session, so the line goes in the packet step the session reads. The new test fails before the change and passes after.

## Result

review_fix script tests pass (181).

## Watch

—

## Back-out

Remove `commit_credit_refusal` and its call from `review/review_fix.py` and the two new tests in `tests/scripts/test_review_fix_script.py`.
