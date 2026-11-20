---
type: "Change"
change_type: "fixed"
title: "review loop reverts a fix coder's approval-only edit and reports it"
description: "The review loop restores a fix coder's edit to CLAUDE.md, CLAUDE.local.md or AGENTS.md to its pre-pass blob and reports it as a dropped ask, and a re-run files no ask for a saved path with no diff against HEAD."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 10
kind: "fix"
components: ["script/review-loop-ruled", "script/review-loop-coder", "script/review-loop-script", "script/full-check-gate", "script/script-utils"]
evidence: ["review-re-run-files-a-user-only-claude-md-ask-for"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::ApprovalEditRevertTest::test_an_edit_to_claude_md_is_reverted_reported_and_files_no_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

`ask_for_approval_only_edits` calls `revert_approval_edit`: each approval-only file the pass changed goes back to its pre-pass blob (a created file is removed) and lands in `dropped_asks` with `REVERTED_APPROVAL_EDIT_REASON`. A file that cannot be hashed or restored is still filed as an ask. `resume_approval_asks` skips a saved path that matches HEAD or a kept held packet holds. `without_reverted` drops the reverted file from the pass's diff stat. A finding filed on a reverted approval-only path stays an open fix on every repair path (round, coder0, class, prose, gate, lint), never fixed or skipped_fp; a class member left open this way counts in `open_classes`.

## Evidence

A fix coder's CLAUDE.md edit was filed as a user-only ask the user does not answer, and a re-run filed it again after the session had reverted the file.

## Result

`ApprovalEditRevertTest` and the new `ApprovalAskResumeTest` cases in `test_review_loop_ruled.py`.

## Watch

None.

## Back-out

Revert the commit.
