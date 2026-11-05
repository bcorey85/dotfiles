---
type: "Change"
change_type: "fixed"
title: "The commit gate credits a review that converged in another session of the same repo"
description: "reviewed_tree.record_reviewed also keeps the last 50 reviewed fingerprints per repo in one shared reviewed-trees.json, and is_reviewed credits a commit whose tree matches one of them, so a /code fork, a resumed /code run or a parent session can commit the exact tree another session's review converged on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 6
kind: "fix"
components: ["script/review-commit-gate", "script/reviewed-tree"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_review_that_converged_in_another_session_credits_a_commit_of_the_same_tree"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/reviewed_tree.py` gains `SHARED_REVIEWED_NAME`, `SHARED_LIMIT`, `shared_reviewed_file`, `read_json_object` and `read_shared_reviewed`. `record_reviewed` still writes the per-session record and now also appends the fingerprint to `reviewed-trees.json` under the repo's top level, deduplicated and capped at the last 50, in one atomic write. `is_reviewed` returns true on a per-session match or when the fingerprint is in the shared list of the same repo. The credit stays exact: the fingerprint still leaves out only the notes paths, so an edit after the review, or another repo, gets no credit. The hook itself is unchanged.

## Evidence

judgment: three sessions reported the same defect. A /code fork's converged review did not credit the parent's commit, a `/code resume` lost the earlier fork's record, and a restarted review was needed after a fork. Each new session id read an empty per-session record. The new test fails on the base commit and passes after; two sibling tests pin that an edited tree and another repo still get no credit.

## Result

`test_review_commit_gate.py` 152 of 152 pass; lint clean.

## Watch

—

## Back-out

Revert the shared-record functions and constants in `reviewed_tree.py`, the shared check in `is_reviewed`, and the three tests.
