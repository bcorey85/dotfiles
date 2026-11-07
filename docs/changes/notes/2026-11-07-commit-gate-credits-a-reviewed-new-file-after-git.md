---
type: "Change"
change_type: "fixed"
title: "Commit gate credits a reviewed new file after git add"
description: "The reviewed-tree fingerprint no longer changes when git add stages a new file or a move, so a review that converged on a new untracked file credits the commit after git add stages it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T02:27:55-06:00"}
seq: 2
kind: "fix"
components: ["skill/review", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_tree_fingerprint.py::TreeFingerprint::test_a_staged_new_file_has_the_value_of_the_same_file_untracked"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/reviewed_tree.py` `tree_fingerprint` diffs with `--no-renames --diff-filter=a` and hashes every file the tree adds against base, staged, untracked or committed since base, as one added-file entry. Submodules stay in the diff part; every added symlink is hashed by its link text whether staged, committed or untracked, and an untracked nested repository raises. A new file or symlink has the same value staged or untracked, and a staged `git mv` has the value of the plain move.

## Evidence

judgment: a /code loop converged on a tree with a new untracked module and recorded its fingerprint. The session ran `git add`, and review-commit-gate denied the commit as having no converged /review. A commit that added only docs files, which the reviewed fingerprint leaves out, passed. The new tests fail before the change and pass after.

## Result

Full suite passes. review_commit_gate median 47 ms over 21 runs against a bare Python start of 8 ms. A tree that adds a file through the index or a commit since base hashes differently from before, so a stored verify or review record for such a tree is stale once.

## Watch

—

## Back-out

Revert the added-file hashing in `lib/reviewed_tree.py` and the new tests in `tests/scripts/test_tree_fingerprint.py`, `tests/scripts/test_review_commit_gate.py` and `tests/scripts/test_verify_branch_script.py`.
