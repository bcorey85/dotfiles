---
type: "Change"
change_type: "fixed"
title: "gate env takes a run's values from its own plan alone"
description: "`repo_gate_env` returns only the run's own plan's `NAME=value` words when that plan is readable; values other plans agree on now fill in only for a run with no plan."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:55:06-05:00"}
seq: 82
kind: "fix"
components: ["script/plan-format", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::RepoGateEnvTest::test_the_plan_of_the_run_takes_no_name_that_only_other_plans_set"
asked: ""
proof: []
unmeasured: "The gate-env line of a dispatch is not logged; no intake number reads it."
---

## Change

With a readable plan, the coder prompt's `gate-env:` line, the stored coder gate and verify-prep's env come from that plan
alone. Planless `--task` runs and verify-prep with no plan keep the agreed values of the repo's plans. Task-text or
run-note assignments do not override the plan's line. `repo_gate_env` reads the two cases through `own_plan_gate_env` and
`agreed_gate_env`, which keeps it under the complexity cap the code-step files carry.

## Evidence

In a per-ticket worktree the coder prompt carried another ticket's container name and ports from older plans; the
coder ran a fixture recreate against the other ticket's stack and only a host-port conflict stopped it.

## Result

A plan run never carries another plan's values.

## Watch

None.

## Back-out

Revert the commit.
