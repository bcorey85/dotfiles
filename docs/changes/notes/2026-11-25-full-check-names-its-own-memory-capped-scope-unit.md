---
type: "Change"
change_type: "fixed"
title: "Full check names its own memory-capped scope unit"
description: "A check command that starts with the capped systemd-run prefix now runs inside the full check's own capped scope, where before both scopes got one unit name and the check never started."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T15:18:30-06:00"}
seq: 3
kind: "fix"
components: ["script/memory-cap-scope", "script/check-output", "script/full-check"]
evidence: ["incident", "tests"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::NestedCappedRunTest::test_a_command_that_starts_with_the_capped_prefix_runs_inside_the_capped_shell"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`memory_cap_scope.capped_shell_argv` adds `--unit=capped-<pid>-<random hex>` to the systemd-run argv, so each capped run names a scope unit of its own. The full check, the coder gate and the criteria dry run all build their argv there. `check_output.RUNNER_CANNOT_START` also matches systemd-run's `Failed to start transient scope unit: ` line, so a scope that cannot start reads as a setup fault, not as a failed check.

## Evidence

systemd-run names a scope `run-p<pid>-i<pidfd inode>.scope`. `--scope` and `sh -c` with one command both exec in place, so an inner `systemd-run --scope` (the capped form lanes write) runs as the outer one's pid and gets the outer unit's name: "Failed to start transient scope unit: Unit ... was already loaded". On 2026-11-25 this stopped an agent-evals review loop's full check three times in a row. By hand, the nested form exits 1 with that line, and exits 0 when the outer scope names its own unit.

## Result

The named test runs the capped prefix inside `shell_popen_args` on this machine and fails without the change. `test_check_output.py` covers the setup-fault read, and `CappedUnitNameTest` covers a fresh unit name on each call.

## Watch

—

## Back-out

Revert the branch's commits.
