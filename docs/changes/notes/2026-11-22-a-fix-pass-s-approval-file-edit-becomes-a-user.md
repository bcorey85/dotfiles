---
type: "Change"
change_type: "fixed"
title: "A fix pass's approval-file edit becomes a user-only ask with the wanted change"
description: "After the loop reverts a fix coder's edit to an approval-only file, each finding on that file becomes a user-only ask carrying its proposed change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 25
kind: "fix"
components: ["script/review-loop-ruled", "script/review-loop-script"]
evidence: ["review-fix-coder-edits-a-claude-md-even-when-the"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::ApprovalAskResumeTest::test_a_reverted_claude_md_edit_for_a_finding_becomes_a_user_only_ask_carrying_its_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_loop_ruled.ask_for_approval_only_edits` files one user-only ask per finding on a reverted approval-only path, in place of an open fix. A rejected wanted-change ask is not filed again.

## Evidence

A fix coder edited `scripts/CLAUDE.md` in two /review runs. Each ended with a revert stop that carried no wanted change, and the finding came back open.

## Result

ApprovalAskResumeTest in `test_review_loop_ruled.py`.

## Watch

None.

## Back-out

Revert the commit.
