---
type: "Change"
change_type: "changed"
title: "Plan-review rounds write reviewer reports to files; round two checks them"
description: "Each plan-review round writes every reviewer report to the task directory, and a script check fails round two when a prior round's report file is missing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T15:23:40-05:00"}
seq: 56
kind: "fix"
components: ["skill/eng-spec", "script/plan-review-reports"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_review_reports.py::PlanReviewReportsTest::test_round_two_fails_when_round_one_report_is_missing"
asked: ""
proof: []
unmeasured: ""
---

## Change

The plan-review phase now has the session Write each reviewer hand-back to `review-round<n>-shard-<x>.md` in the task directory right after it arrives. Before round two, `tools/plan_review_reports.py check <task dir> 2` exits 1 and names the missing file when an earlier round has no non-empty report file. Round two reads the prior findings from those files. Before, reports lived only in context, and compaction dropped them.

## Evidence

judgment: a session lost round-one findings to compaction and rebuilt them from the transcript. `test_round_two_fails_when_round_one_report_is_missing` fails before the change (no script) and passes after.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Revert the added lines in `6b-review.md`, delete `plan_review_reports.py` and its test.

