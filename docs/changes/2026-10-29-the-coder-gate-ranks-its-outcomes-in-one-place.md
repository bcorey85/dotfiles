---
type: "Change"
title: "The coder gate ranks its outcomes in one place"
description: "The scoped test run and the hand-back hook rank a mixed result with one gate_outcome(), so a setup fault beside a command error reports a command error in both, and each coder's gate record holds one per-command outcome map."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T09:43:24-05:00"}
seq: 249
kind: "fix"
components: ["script/coder-gate", "script/code-step", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_a_setup_fault_beside_a_command_error_gets_the_same_outcome_from_the_scoped_run_and_the_hook"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `coder_gate.py`: a new `gate_outcome()` ranks failed > command error > setup fault > timeout > pass, and both
  `run_scoped_tests` and `run_hook` use it. A command error names a path that does not exist, so the command is
  wrong whatever the environment is; `sort_failures` already classes a command that shows both signs as one.
- The gate file stores each coder as `{runs, denies, result, commands: {command: {outcome, detail}}}`, in place of
  eight parallel lists. `stamped_handback`, `clear`, `code_step_report.tests_run_text` and `code_step.coder_flagged`
  read the map; their text is unchanged. An old-format coder keeps its runs and denies and gets the map on its next
  hook run.
- `script_utils.details_with_outcome` picks the `{command: detail}` pairs for one outcome.

## Evidence

- `run_scoped_tests` ranked setup fault above command error, and `run_hook` ranked command error first, so the same
  mixed result read as a setup fault in one path and a command error in the other.

## Result

- The named test fails before (`'command-error' != 'setup-fault'`) and passes after.
  `test_coder_gate.py::CoderGateEnvironmentTests::test_a_coder_stored_with_the_old_command_lists_keeps_its_counts_and_gets_the_commands_map`
  pins the old-format upgrade.

## Watch

—

## Back-out

Revert the commit.
