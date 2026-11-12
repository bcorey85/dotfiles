---
type: "Change"
change_type: "fixed"
title: "a converged /review of the uncommitted change counts as the branch review once one was logged"
description: "verify-prep and verify-log count the branch review as ran when one was logged on an earlier tree and a converged /review covers the work tree's uncommitted change against HEAD, or the last commit's change against HEAD~1 once committed (never the empty change, never when HEAD is a merge)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:00:14-06:00"}
seq: 13
kind: "fix"
components: ["script/verify-prep", "script/verify-log", "script/verify-common", "script/reviewed-tree"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_converged_review_of_the_edited_tree_keeps_the_logged_branch_review_counting"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/reviewed_tree.py` gains `shared_record_covers(repo_dir)`: True when the work tree's uncommitted change against HEAD
is in the shared record any session wrote. On a tree with no change against HEAD it reads the change the last commit
made instead (the tree against HEAD~1, notes paths left out), so the credit survives committing the reviewed change
(never when HEAD is a merge); the empty-change value never counts. `verify_common.review_state` takes the repo top and
counts the review as ran, with the reason `branch review logged on an earlier tree; a converged /review covers this
tree`, when the ledger lists a branch review on another tree (or, with the ledger unread, the saved context holds
`reviewLoggedTree`) and the shared record covers the tree. A converged review with no branch review logged earlier does
not count. verify-prep and verify-log pass the top.

## Evidence

judgment: a branch review logged on a tree, coder fixes left uncommitted, then a converged /review whose fix rounds
changed the tree: verify-prep asked for another branch review each time and the loop never closed.

## Result

The new tests pass; they were not run against the old tree. The verify-branch, verify_common and reviewed_tree test files pass.

## Watch

None: a fixed rule over two recorded facts.

## Back-out

Revert the commit.
