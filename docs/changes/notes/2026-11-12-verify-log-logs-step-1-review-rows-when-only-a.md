---
type: "Change"
change_type: "fixed"
title: "verify-log logs Step 1 review rows when only a commit review covers the tree"
description: "verify-log review refuses a second branch review only when a branch review already covers the tree, not when only a converged commit review does."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T16:26:52-06:00"}
seq: 8
kind: "fix"
components: ["script/verify-log", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::OpenAskTest::test_the_step_1_rows_log_when_only_a_converged_commit_review_covers_the_tree"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify-log` `log_review`: the "already counts" refusal fires only when the review state verify-log computes for the tree as it stands is `ran` and not
`coveredByCommitReview`. A Step 1 review run on a tree a converged commit review covers now logs its rows.

## Evidence

judgment: a /verify-branch Step 1 review found and fixed defects, and verify-log exited 2 on its rows because a
commit review covered the tree, so the findings went unlogged.

## Result

The new test exits 2 on the old tree and passes; `test_verify_branch_script.py` passes (161 tests).

## Watch

None: a fixed refusal rule.

## Back-out

Revert the commit.
