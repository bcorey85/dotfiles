---
type: "Change"
title: "The hand-back gate finds a subfolder manage.py and names a missing test path as a command error"
description: "The gate builds `manage.py test` from a manage.py in a subfolder with labels from that folder, and a gate command that stops on a path that does not exist is a command error that never denies or spends the cap, flagged apart from the cap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T14:00:00-05:00"}
seq: 159
kind: "fix"
components: ["script/code-step", "script/coder-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_a_missing_test_path_is_a_command_error_that_never_spends_a_deny"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The gate reads a listed `<python> <dir>/manage.py test` command, and finds a manage.py in the folder above the
  phase's Python files when none is listed. It runs `<dir>/manage.py test` with labels from `<dir>`, and drops test
  files outside it. `pipenv` and `pdm` commands count as verification commands.
- coder_gate reads a failure whose output names a path missing where the command ran (pytest `file or directory not
  found`, python `can't open file`, a shell or `cd` error) as a command error. It never denies the hand-back or spends
  the cap; a run with only command errors has the result `command-error`, and the stamp names each one.
- code-step flags each command error apart from the cap, as no code failure, and tests-run names it.
- The missing-path patterns moved from full_check to `check_output`, which both gates read.

## Evidence

- A /code round ended `flagged: hand-back gate cap` on `python3 -m pytest` with paths from two roots, in a repo whose
  plan named `pipenv run python <sub>/manage.py test`. The same tests passed under the repo's runner.
- The new tests fail on the old scripts.

## Result

- A gate command with a wrong path no longer spends three denials or reads as failing code.

## Watch

—

## Back-out

Revert the commit.
