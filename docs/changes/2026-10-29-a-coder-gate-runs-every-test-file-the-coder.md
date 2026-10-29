---
type: "Change"
title: "A coder gate runs every test file the coder creates when the phase names none"
description: "The derived coder-gate test command for a phase that names no test file now runs every changed file that `is_runnable_test_file` counts as a test (foo.spec.js, foo.test.mts, __tests__/foo.jsx under jest, test_foo.py), through a new `{tests}` placeholder, in place of a fixed suffix list that missed them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T07:12:59-05:00"}
seq: 247
kind: "fix"
components: ["script/code-step", "script/coder-gate"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_script_phase_naming_no_test_file_runs_every_test_file_the_coder_creates"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `coder_gate.py`: a command may hold `{tests}` or `{tests:<suffixes>}`, filled like `{files}` but keeping only
  changed files that `source_paths.is_runnable_test_file` counts as tests (it leaves out conftest, `__init__` and
  support files under `tests/`). `{jest-tests}` also keeps the script files under `__tests__/`, which jest runs and
  vitest does not.
- `code_step_gates.py`: the pytest and script test checks use `is_runnable_test_file`; `TEST_FILE` and
  `TEST_SUFFIXES` are gone. A script phase that names no test file falls back to
  `{tests:.ts,.tsx,.mts,.js,.jsx,.mjs}` (`{jest-tests:...}` under jest), a Python phase to `{tests:.py}`. A
  `manage.py test` phase keeps Django's own `test*.py` name rule, so `tests_views.py` keeps its run. The eslint
  suffix set drops a dead union.
- `source_paths.py`: `is_test_path` and `is_runnable_test_file` share one name rule that counts `tests.py` and `test.py`, so
  they no longer count as source, and a Django phase that names `app/tests.py` keeps its `manage.py test app.tests`
  run.

## Evidence

- The fallbacks kept only `.test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx` and `_test.py`: a coder-created
  foo.spec.js, foo.test.mts, __tests__/foo.jsx or test_foo.py got no gate run.
- The tests that fail on the base scripts and pass now:
  `test_code_step.py::CodeStepTest::test_a_script_phase_naming_no_test_file_runs_every_test_file_the_coder_creates`
  and `test_a_python_phase_naming_no_test_file_runs_every_test_file_the_coder_creates`.
  `test_a_django_phase_runs_the_tests_module_it_names` pins the Django `tests.py` and `tests_views.py` labels, and
  `test_a_jest_phase_naming_no_test_file_also_runs_the_script_files_the_coder_creates_under_tests` the jest
  `__tests__/` case.

## Result

- One shared test-file rule in the coder gate, plus Django's own pattern for `manage.py test`; every coder-created
  test file its runner can take runs at hand-back.

## Watch

- None: no intake counts test files the gate skipped.

## Back-out

- Revert the commit.
