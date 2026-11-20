---
type: "Change"
change_type: "fixed"
title: "An accepted user-only ruling clears its path from the saved approval asks"
description: "A user-only approval ask ruled accepted, modified or rejected drops its path from approval-asks.json, so the next loop does not file the same edit again."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-17T22:49:28-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop", "script/phase-asks", "script/review-fix-asks", "script/review-asks"]
evidence: ["review-loop-re-asks-an-accepted-user-only-approval"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::ApprovalAskResumeTest::test_a_second_loop_after_an_accepted_user_ruling_files_no_ask_for_the_edit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `approval_asks_store.forget_ruled_approval_paths` (was `forget_rejected_approval_paths`) drops the path of every ruled user-only ask, whatever the outcome. `phase_asks.py rule`, `asks-done` and `asks-done --correct` call it. A damaged file still stops the ruling with nothing logged.
- The dead `../code` entries in the `sys.path` lines of `phase_asks.py` and `review_asks.py` are gone.

## Evidence

An accepted ask stayed in the saved file, so a second loop filed the same approval ask again.

## Result

A second loop after an accepted ruling files no ask for the edit (`test_a_second_loop_after_an_accepted_user_ruling_files_no_ask_for_the_edit`).

## Watch

None.

## Back-out

Revert the commit.
