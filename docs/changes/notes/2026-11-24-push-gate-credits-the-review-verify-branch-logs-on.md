---
type: "Change"
change_type: "fixed"
title: "Push gate credits the review verify-branch logs on its own fix commit"
description: "verify-log review records the tree it logged in the reviewed-tree record, so the push gate allows the push of the tree verify-branch reviewed"
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T16:17:46-06:00"}
seq: 2
kind: "fix"
components: ["skill/verify-branch", "script/verify-log"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::ReviewLogTest::test_the_push_gate_credits_the_review_logged_on_the_tree_its_own_fix_commit_leaves"
asked: ""
proof: []
unmeasured: "no intake number reads one blocked push"
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`verify-log review` now records the reviewed tree (`reviewed_tree.record_reviewed`) after it logs the review. Before, a push after verify-branch fixed a finding and committed was refused for a missing fresh review and cost one extra review run; now that push goes through, and any later unreviewed commit is still refused.

## Evidence

Two lanes on 2026-11-23 hit the refused push right after /verify-branch committed its own fix.

## Result

The new test failed before the change (push state `changed`, expected `reviewed`) and passes after; the full suite passes.

## Watch

None.

## Back-out


`git revert` the commit.
