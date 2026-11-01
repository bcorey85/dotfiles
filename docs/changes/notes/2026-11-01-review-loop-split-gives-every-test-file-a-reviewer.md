---
type: "Change"
change_type: "fixed"
title: "review loop split gives every test file a reviewer"
description: "When a wide change splits its code review in two, the split halves the files the first code reviewer owned, so test files keep a reviewer when no test reviewer runs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:56:52-06:00"}
seq: 429
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_split_change_with_no_test_reviewer_gives_every_test_file_a_reviewer"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `first_round_plan` splits the first code reviewer's owned files in two, in place of the source files only.

## Evidence

judgment: a bug hunt on master 22c42b39 found that a change of three small source files and three large test files
(over the split bar, under the large bar) sent two code reviewers over the source files and no reviewer over the
test files.

## Result

The named test fails before (the three test files have no owner) and passes after. `test_review_loop_script` and
`test_change_size_bar`: 207 tests, 0 failed; ruff clean.

## Watch

None. The plan is a pure function the test covers.

## Back-out

Revert the split in `first_round_plan` to halve `source`, and remove the test.
