---
type: "Change"
change_type: "fixed"
title: "The review loop skips findings on files absent from the tree"
description: "A reviewer finding whose file:line names a file neither on disk nor listed by git goes to skipped_fp and never reaches the coder; a plan-change ask still stops the loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 191
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_finding_on_a_file_absent_from_the_tree_is_skipped_and_never_sent_to_the_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_findings.py` `absent_file_split`: splits a review's fix, ask and nit items whose path is not on disk
  and matches no tracked or untracked path. `review_loop_script.py` files them under `skipped_fp` with the reason "the
  file is not in the tree". A plan-change ask stays in the review.

## Evidence

- Queue item code-review-lists-findings-on-files-absent-from: the hand-back listed fixes on files the branch never had.
- The new test fails on the old script: the coder gets the absent-file finding.

## Result

- No finding on a missing file is sent to the coder or listed as fixed.

## Watch

—

## Back-out

Revert the commit.
