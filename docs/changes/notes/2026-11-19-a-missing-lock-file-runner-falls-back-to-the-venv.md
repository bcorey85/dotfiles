---
type: "Change"
change_type: "fixed"
title: "a missing lock-file runner falls back to the venv and is named as an environment gap"
description: "With a lock file but its runner off PATH and a project venv present, gate and discovered commands use the venv python; a check that exits 127 on a missing tool is an environment gap that names the tool."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 2
kind: "fix"
components: ["script/gate-commands", "script/check-output", "script/criteria-verdict", "script/full-check", "script/coder-gate", "script/criteria-dry-run"]
evidence: ["code-hand-back-gate-faults-when-pipenv-is-absent", "review-loop-full-suite-check-fails-when-pipenv-is", "criteria-dry-run-pipenv-checks-broken-in-fresh"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_missing_tool_is_an_environment_gap_naming_the_tool_not_a_failure"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/gate_commands.py` uses the project `.venv`/`venv` python when `Pipfile.lock` (or another lock-file runner) is
present and the tool is not on PATH. `lib/check_output.py` names the tool a shell or shim could not find on an exit
127. The full check reports `not run (environment gap: ...)`, the hand-back gate's setup-fault stamp names the tool
and does not count, and the criteria dry run gives ENV, never BROKEN.

## Evidence

The hand-back gate stopped as a setup fault on a missing pipenv while the project venv ran the tests.

## Result

New tests in `test_gate_commands.py`, `test_check_output.py` (MissingToolTest), `test_full_check.py`,
`test_coder_gate.py` and `test_criteria_dry_run.py`.

## Watch

None.

## Back-out

Revert the commit.
