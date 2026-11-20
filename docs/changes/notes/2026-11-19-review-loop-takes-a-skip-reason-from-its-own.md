---
type: "Change"
change_type: "fixed"
title: "review loop takes a skip reason from its own finding and restores plan-named tests"
description: "A skipped finding's status and reason now come from the same finding, and a fix pass that deletes a test the plan runs by name gets one restore pass before the scoped-tests check."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:11-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop-script", "script/code-step"]
evidence: ["review-loop-mislabels-skipped-findings-and-deletes"]
watches: []
test: "tests/scripts/test_review_loop_script.py::SkipLabelsTest::test_a_finding_folded_into_a_merged_skipped_item_takes_its_status"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/coder_report.py` `skipped_issues` pairs each skip line with the finding it covers, so a merged or chained skip
keeps its own reason. `lib/named_test_targets.py` reads the test files and node ids the plan's commands name; the new
`review/review_loop_named_tests.py` lists them in the coder prompt and runs one restore pass when a fix pass deletes
one.

## Evidence

The loop printed one finding's skip reason against another, and a reviewer-driven fix deleted a test a criterion
named.

## Result

`SkipLabelsTest` in `test_review_loop_script.py`, `test_named_test_targets.py`, and
`test_review_loop_named_tests.py::NamedTestsLoopTest::test_a_fix_pass_that_deletes_a_plan_named_test_gets_one_restore_pass`.

## Watch

None.

## Back-out

Revert the commit.
