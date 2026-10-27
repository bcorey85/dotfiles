---
type: "Change"
title: "Split command steps keeps a quoted operator in its step"
description: "A quoted |, &&, || or ; stays inside its step, so a search pattern that names a check tool is no longer read as a run of it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T00:19:18-05:00"}
seq: 45
kind: "fix"
components: ["script/quality-check-cap", "script/rg-path-gate", "script/shell-command"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_search_pattern_naming_a_check_is_not_a_run_of_it"
asked: ""
proof: []
unmeasured: "A bug fix with a failing-before test; no intake number reads a wrongly denied search."
---

## Change

split_command_steps skips an operator that sits inside single or double quotes or after a backslash. Callers: quality_check_cap and rg_path_gate; no security hook calls it. Also pinned in tests/scripts/test_shell_command.py::SplitCommandStepsTest::test_a_quoted_operator_stays_inside_its_step.

## Evidence

The new tests fail on the base tree and pass on the fix; the shell_command, quality_check_cap and rg_path_gate suites pass.

## Result

`rg -n -i 'typecheck|tsc|lint' a b | head -20` is two steps and is allowed after a tsc run.

## Watch

None.

## Back-out

Restore the single OPERATOR.split in split_command_steps.

