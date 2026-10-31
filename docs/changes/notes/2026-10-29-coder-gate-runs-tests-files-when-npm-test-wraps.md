---
type: "Change"
change_type: "fixed"
title: "Coder gate runs __tests__ files when npm test wraps jest"
description: "A package with no jest or vitest dependency whose test script names jest or react-scripts now gets the jest test-file rule, so a coder-created __tests__ file is in the derived npm test command."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T10:08:34-05:00"}
seq: 252
kind: "fix"
components: ["script/code-step", "script/coder-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_npm_test_script_that_wraps_jest_also_runs_the_script_files_the_coder_creates_under_tests"
asked: ""
proof: []
unmeasured: "No intake counts test files the gate skipped."
---

## Change

- `code_step_gates.py`: with no vitest or jest dependency, a `test` script that names `jest` or `react-scripts` sets
  the jest flag, so the `npm test -- {jest-tests:...}` fallback keeps script files under `__tests__/`. The test-file
  rule itself stays in `source_paths.is_runnable_test_file`; only the flag changes. A test script naming neither keeps
  the `{tests:...}` placeholder.

## Evidence

- Before the change, `"test": "react-scripts test"` with no jest dependency gave `npm test -- src/foo.spec.js` and left
  out a coder-created `src/__tests__/foo.js`.
- `test_code_step.py::CodeStepTest::test_an_npm_test_script_that_wraps_jest_also_runs_the_script_files_the_coder_creates_under_tests`
  fails on the base script (react-scripts and jest cases) and passes now; its third case, a mocha test script, keeps
  the placeholder.

## Result

- A coder-created `__tests__` file runs at hand-back when the package's npm test script wraps jest.

## Watch

- None: no intake counts test files the gate skipped.

## Back-out

- Revert the commit.
