---
type: "Change"
change_type: "changed"
title: "The quality-check cap and the full check name a tree by its fingerprint"
description: "quality_check_cap sees an untracked file's content change, and the full-check result prints the fingerprint of the tree it checked, both through reviewed_tree.tree_fingerprint."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T23:40:00-05:00"}
seq: 306
kind: "fix"
components: ["script/quality-check-cap", "script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_tree_identity_callers.py::TreeIdentityCallers::test_untracked_file_change_gives_every_caller_a_new_fingerprint"
asked: ""
proof: []
unmeasured: "No intake number reads tree identity; the change removes a second hashing scheme."
---

## Change

`quality_check_cap.git_state_hash` returns HEAD and `reviewed_tree.tree_fingerprint` of the repo; its own diff and
untracked-name-list hash is deleted. An edit to an untracked file's content now counts as a tree change, so a check
rerun after it is allowed. A repo with no commit yet is fingerprinted against git's empty tree. verify-prep already took its fingerprint from the shared function through verify_common.

`full_check.py` prints `tree: <fingerprint>` right after the `full check:` line: the repo's tree as the check left it,
with the log file left out. The line is absent when the repo cannot be fingerprinted (a note goes to stderr).

## Evidence

A read-only scan found four ways the toolkit named a tree.

## Result

A new test gives an untracked file new content and checks that the reviewed-tree, quality-cap, verify and full-check
callers each return a new value, and that all four agree on an unchanged tree.

## Watch

None; a refactor with no intake number.

## Back-out

Revert the commit.
