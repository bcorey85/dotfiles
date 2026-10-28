---
type: "Change"
title: "tests/run.sh ends on a line naming each failed step"
description: "When lint, the duplicate check or the tests fail, tests/run.sh ends on a FAILED line naming each failed step, after the test summary, so a lint failure no longer ends on a line that reads as a pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T17:26:09-05:00"}
seq: 117
kind: "fix"
components: ["script/run-sh"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_run_sh.py::RunShTest::test_a_failed_lint_ends_the_run_on_a_line_naming_it_after_a_passing_test_summary"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tests/run.sh` collects each failed step (`lint`, `duplicate-check`, `tests`) and, when any failed, prints
  `FAILED: <steps>` as its last line before it exits 1.

## Evidence

- A suite run exited 1 on an E501 lint error, but its last line read "3177 tests in 86 files ... 0 failed". The
  orchestrator read only that line and shipped the change to master.
- The new test runs run.sh with a failing ruff stub and a passing test summary. On the old script the last line is the
  test summary, so the test fails.

## Result

- A run with a failed lint or duplicate check ends on a line that names the failure.

## Watch

—

## Back-out

Revert the commit.
