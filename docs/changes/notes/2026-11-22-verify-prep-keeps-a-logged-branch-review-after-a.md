---
type: "Change"
change_type: "fixed"
title: "verify-prep keeps a logged branch review after a change-note-only commit"
description: "A commit that changes only files under docs/changes/ no longer makes a logged branch review read as not run: verify-prep's tree fingerprint leaves that folder out, and any other change still changes it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:13:23-06:00"}
seq: 24
kind: "fix"
components: ["script/verify-prep", "script/reviewed-tree"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_prep_shared_rules.py::ReviewNeutralFolderTest.test_a_commit_that_changes_only_a_change_note_keeps_the_fingerprint"
asked: ""
proof: []
unmeasured: "No intake number reads it; the queue item that reported it is the evidence."
---

## Change

`reviewed_tree.tree_fingerprint` takes `exclude_prefixes`, folders left out of both the diff and the added-file hashes. `verify_common.REVIEW_NEUTRAL_FOLDERS = ("docs/changes/",)` sits beside the fingerprint partial verify-prep and verify-log both hash through; it is the only review-neutral path list. docs/ notes elsewhere, plans and code still count.

## Evidence

A lane committed a reviewed tree plus an edit to one change note; verify-prep then reported the branch review as not run and a third review was dispatched to clear it.

## Result

New tests fail on the old tree (fingerprint changes after a note-only commit) and pass now; a code edit and a docs/other note edit still change the fingerprint. A fingerprint logged before this change on a branch holding docs/changes files will not match once, and that branch needs one re-log.

## Watch

None.

## Back-out

Revert the commit: the constant and the `exclude_prefixes` argument go.

