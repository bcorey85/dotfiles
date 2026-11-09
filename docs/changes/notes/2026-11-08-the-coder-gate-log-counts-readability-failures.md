---
type: "Change"
change_type: "changed"
title: "The coder gate log counts readability failures"
description: "Each coder-gate.jsonl row the hand-back gate writes carries readability_failed, the number of failing readability-check commands in that run, so the intake can count readability denials per coder dispatch from metadata alone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T23:40:23-06:00"}
seq: 15
kind: "fix"
components: ["script/coder-gate"]
evidence: ["log gap"]
watches: ["coder-readability-handback-denials"]
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_a_denial_by_a_readability_hit_logs_one_readability_failure"
asked: ""
proof: []
unmeasured: ""
---

## Change

`coder_gate.py`: `GateCounts` gains `readability_failed`, the count of real failures whose command is the readability check. `log_gate_run` writes it on every gate-run row (0 when none). The bash hook's `whole-package-deny` row is unchanged.

## Evidence

The gate log said a run was denied and how many commands failed, never which. A readability denial could not be told from a red test, so no intake could read the readability hand-back gate's denial rate.

## Result

`test_a_denial_by_a_readability_hit_logs_one_readability_failure`, `test_a_denial_by_a_failing_other_command_logs_no_readability_failure` and `test_a_readability_hit_and_another_failing_command_log_only_the_hit_as_readability` fail before (KeyError) and pass after. `bash tests/run.sh`: 3230 tests, 0 failed.

## Watch

`coder-readability-handback-denials`: readability denials per gated coder dispatch, good direction down. Rows written before this field are left out of both counts.

## Back-out

Revert the commit; the intake reader then leaves every row out.
