---
type: "Change"
change_type: "fixed"
title: "code_review_start accepts an ancestor base on resume and leaves merges out"
description: "code_review_start accepts a --base that is an ancestor of the recorded head, or the current HEAD when the recorded head is an ancestor of it, refuses another base naming the flag, and leaves merge commits from the integration branch out of the review diff through a merge-free synthetic base."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 11
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["code-review-start-rejects-a-resume-time-review"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_merge_commit_after_the_phase_is_left_out_of_the_review_diff"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_review_start.py` checks the passed base against the recorded head. The new `lib/merge_free_base.py` builds a
base that folds in merges from the integration branch; a merge that cannot fold stops the run and names it. Folding a
user-resolved merge is not built; the plan records that ruling.

## Evidence

A resume-time review with a correct `--base` was refused, and integration merges filled the review diff.

## Result

Base tests in `test_code_review_start.py` and `test_phase_start.py`, and `test_merge_free_base.py`.

## Watch

None.

## Back-out

Revert the commit.
