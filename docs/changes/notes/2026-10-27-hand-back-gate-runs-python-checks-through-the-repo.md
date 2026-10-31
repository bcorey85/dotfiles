---
type: "Change"
change_type: "fixed"
title: "Hand-back gate runs Python checks through the repo's runner and does not deny on setup faults"
description: "The coder hand-back gate builds its pytest and ruff commands from the phase's listed pytest command, else the repo's lock file or virtualenv, and a failure that shows the environment cannot run a check is reported as a setup fault that never denies or counts toward the cap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T13:05:39-05:00"}
seq: 91
kind: "fix"
components: ["script/code-step", "script/coder-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_a_module_missing_from_outside_the_repo_never_spends_a_deny"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_gates.python_commands` takes a runner: the words before `pytest` in the first pytest command the phase's
  Automated Verification lists (a command with `cd` or a chain before pytest gives none), else `uv run`,
  `poetry run`, `pdm run` or `pipenv run` from the repo's lock file, else `.venv/bin/python -m` or `venv/bin/python -m`,
  else `python3 -m` as before. Ruff runs through the same runner, except a bare system python.
- `coder_gate.py` splits each failed command into a real failure or a setup fault. A setup fault is exit 126 or 127,
  a uv or poetry "cannot start" message, or a missing module from outside the repo with no failed test. A missing repo
  module and "cannot import name" stay real failures.
- A setup fault never denies and never counts toward the cap. A run with only setup faults has the result
  `setup-fault`; the stamp names each command with its output tail, and the /code report reads "could not run at the
  hand-back gate (setup fault), no test result". The gate log row gains a `setup_faults` count.

## Evidence

- One work sighting: in a Python repo whose tests run inside a managed virtualenv, the gate ran a bare
  `python3 -m pytest`, denied the hand-back 3 times, and hit its cap. The repo's own runner then passed the full suite.
  The run spent all its denials on a wrong command and reported a test failure that was not real.
- It fires on every /code phase in any such repo.
- The three new setup-fault tests fail on the base commit and pass after; the runner tests pin the derived commands.

## Result

- Full suite: see the install commit.

## Watch

— (a fix; its test is the check)

## Back-out

Revert the commit. Gate files written before it carry no `setup_faults` key, and every reader defaults it to none.
