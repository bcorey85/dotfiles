---
type: "Change"
change_type: "fixed"
title: "gates run checks with the main checkout's python version"
description: "The full check, the hand-back gate and the criteria dry run put the pyenv shims first and select the main checkout's .python-version in a linked worktree; herdr-worktree links a gitignored .python-version into a new worktree."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 1
kind: "fix"
components: ["script/full-check", "script/coder-gate", "script/criteria-dry-run", "script/herdr-worktree"]
evidence: ["review-loop-full-suite-check-fails-when-pipenv-is", "criteria-dry-run-pipenv-checks-broken-in-fresh", "herdr-worktree-carry-gitignored-python-version"]
watches: []
test: "tests/scripts/test_gate_env.py::CheckEnvTest::test_a_worktree_with_the_pin_only_in_the_main_checkout_gets_its_version_and_the_shims_first"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/gate_env.py` owns `check_env`: the pyenv shims go first on PATH, and `PYENV_VERSION` comes from the main
checkout's `.python-version` when the worktree has no pin of its own. `review/full_check.py`, `code/coder_gate.py`
and `tools/criteria_dry_run.py` run their commands in that env. `herdr-worktree` symlinks a gitignored
`.python-version` from the main checkout into the new worktree; a tracked or non-ignored file is not linked.

## Evidence

A fresh worktree has no gitignored `.python-version`, so pyenv fell back to a python with no pipenv, and every
pipenv check failed as a setup fault or BROKEN.

## Result

`test_gate_env.py` CheckEnvTest, new tests in `test_full_check.py`, `test_coder_gate.py`, `test_criteria_dry_run.py`
and `test_herdr_worktree.py`.

## Watch

None.

## Back-out

Revert the commit.
