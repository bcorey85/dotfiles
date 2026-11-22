---
type: "Change"
change_type: "fixed"
title: "verify-prep keeps a branch review current when only change notes were added"
description: "verify-prep and verify-log leave committed change-note paths out of the tree fingerprint, so notes written after the branch review do not ask for a second review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:08-06:00"}
seq: 21
kind: "fix"
components: ["script/verify-prep", "script/verify-common"]
evidence: ["change-notes-written-at-branch-end-make-the-branch"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_change_note_written_after_the_review_keeps_it_current_and_a_code_edit_stales_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify-prep` saves the committed notes entries in the verify context, and `verify_common.context_fingerprint` passes them to `tree_fingerprint`. A code change still makes the review stale.

## Evidence

A lane wrote `docs/changes` notes after its logged branch review, and verify-prep asked for a second branch-wide review over doc-only additions.

## Result

PrepTest in `test_verify_branch_script.py`.

## Watch

None.

## Back-out

Revert the commit.
