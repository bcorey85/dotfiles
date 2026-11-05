---
type: "Change"
change_type: "fixed"
title: "full check runs a shell-wrapper manage.py through its shell"
description: "check_discovery.py runs a repo-root manage.py whose `#!` line names a shell (not Python) through that shell under the project runner (`pipenv run bash manage.py test --noinput`), so the wrapper's `python` resolves to the runner's environment and the discovered full check no longer dies on a SyntaxError."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:38:01-06:00"}
seq: 7
kind: "fix"
components: ["script/check-discovery", "script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_check_discovery.py::CheckDiscoveryTest::test_a_shell_wrapper_manage_py_runs_through_its_shell_not_python"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_discovery.py` gains `wrapper_shell(script)` (the shell a `#!` line names when it names no Python; `#!/usr/bin/env bash` gives bash) and `manage_py_words(repo_dir, runner)`. A wrapper runs as `<runner> <shell> manage.py`; the runner's environment words are dropped for a bare `python3 -m` or venv runner. A manage.py with a Python `#!` line or none runs through python as before. `check_scope` scores the wrapper step `none`, which the receipt accepts (only `targeted` test steps fail it).

## Evidence

judgment: four sessions reported the review full check running `pipenv run python manage.py test --noinput` on a repo-root bash wrapper around `backend/manage.py`, failing with SyntaxError at line 3 and stopping the loop on a check that never ran. The named test fails on the base commit and passes after.

## Result

`test_check_discovery.py` 13 of 13, `test_full_check.py` 71 of 71 pass; lint clean.

## Watch

—

## Back-out

Revert `wrapper_shell`, `manage_py_words` and their call in `python_part_commands`, and the two tests.
