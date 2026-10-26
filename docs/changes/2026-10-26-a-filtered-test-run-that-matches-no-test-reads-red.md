---
type: "Change"
title: "A filtered test run that matches no test reads RED in the eng-spec dry run"
description: "The dry-run script marks a filtered test run RED unless the output reports at least one passed test."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T00:21:00-05:00"}
seq: 41
kind: "fix"
components: ["script/criteria-dry-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_dry_run.py::CriteriaDryRunTest::test_a_filtered_run_that_matches_no_test_is_red"
asked: ""
proof: []
unmeasured: "A zero-test criterion that reads GREEN is not logged as its own number."
---

## Change

`criteria_dry_run.py` counts the `N passed` lines (pytest, vitest, jest, cargo) and the go package lines that ran tests. A test command with a filter (`-k`, `-t`, `-run`, `--testNamePattern`, `--grep`, `--filter`, a `file::test` id, a cargo name) that exits 0 with no passed test is marked RED, with a FLAG that says it matches no test. A filter that matches a test stays GREEN.

## Evidence

judgment: vitest, jest and cargo exit 0 when a filter matches nothing, so a criterion for a test that is not yet written read GREEN and the coder could pass it with no check running. Tests: `test_a_filtered_run_that_matches_no_test_is_red` and `test_a_filtered_run_that_reports_a_passed_test_is_green`. Both fail on the base commit, where the script does not exist.

## Result

Scoped tests and ruff pass. The code-step verification runner is not changed: it still judges a filtered run by exit code.

## Watch

—

## Back-out

Remove `matches_no_test` and its call in `verdict_for`.
