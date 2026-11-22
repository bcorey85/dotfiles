---
type: "Change"
change_type: "fixed"
title: "An accepted approval-file ask restores the pre-pass text, not HEAD"
description: "When the user accepts reverting a fix coder's edit to an approval-only file, the loop restores the saved pre-pass blob and keeps the user's uncommitted lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 24
kind: "fix"
components: ["script/review-loop-ruled", "script/phase-asks", "script/approval-restore"]
evidence: ["accepted-claude-md-approval-ask-reverts-the-file"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::ApprovalAskResumeTest::test_an_accepted_approval_ask_restores_the_pre_pass_text_and_not_head"
asked: ""
proof: []
unmeasured: ""
---

## Change

A user acceptance of an approval ask restores the file from its saved pre-pass blob and leaves the ask out of the coder's findings. An unknown base still goes to the coder. A failed restore exits non-zero and logs nothing. When the saved blob was pruned by `git gc`, the error says so and names the file and blob id, and the file must be restored by hand.

## Evidence

Accepting "revert the fix coder's edit to CLAUDE.md" let the next coder reset the file to HEAD, which removed uncommitted lines the user had kept.

## Result

ApprovalAskResumeTest in `test_review_loop_ruled.py`, ApprovalRestoreRulingTest in `test_review_fix_ask_ruler.py`, and the restore tests in `test_phase_asks.py`.

## Watch

None.

## Back-out

Revert the commit.
