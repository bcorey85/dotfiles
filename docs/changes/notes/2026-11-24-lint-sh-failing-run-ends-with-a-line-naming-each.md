---
type: "Change"
change_type: "fixed"
title: "lint.sh failing run ends with a line naming each failing step"
description: "A failing tests/lint.sh run now ends on a line that names each failed step and its error count, and the report-only complexity step no longer prints a bare Found N errors line, so a session no longer reads a failing lint as a pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:53:45-06:00"}
seq: 1
kind: "fix"
components: ["script/lint", "script/tests-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_lint_script.py::LintScriptTest::test_a_failing_full_run_ends_with_a_line_naming_the_failed_step"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Each lint step runs through one helper that streams ruff's output and reads its `Found N error(s).` line. A failing
run's last stdout line is `lint failed: <step> (<N> error[s])`, one entry per failed step (`ruff rules`, `complexity
gate`), or `(failed, no error count)` when no count can be read. The report-only C901 step runs ruff with `--quiet` and
prints `complexity report only (N function[s] over the limit): not a failure`. Exit codes are unchanged.

## Evidence

Judgment from one sighting: a toolkit-fix session saw one E501 printed first, then the complexity report's "Found 19
errors" and "All checks passed!", read the lint as passed, and ran the full suite twice (about 8 minutes each) to find it.

## Result

Five new tests in test_lint_script.py; the given-files, full-run and two-failed-steps tests fail on the old lint.sh and
pass now. The file's 14 tests pass.

## Watch

None: tests pin it.

## Back-out

Revert the commit.
