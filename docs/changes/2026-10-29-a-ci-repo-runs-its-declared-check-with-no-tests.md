---
type: "Change"
title: "A CI repo runs its declared check with no tests"
description: "In a repo whose CLAUDE.md holds `Full suite: CI`, full_check.py runs the `Quality check:` command, and an exit 0 with no runner summary passes as a check-only result, so the /code gate runs there instead of reporting `not run (CI)`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T13:00:06-05:00"}
seq: 263
kind: "fix"
components: ["script/full-check", "script/review-loop-script", "script/handback", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_the_declared_check_of_a_repo_whose_full_suite_runs_in_ci_runs_as_a_check_with_no_tests"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `full_check.py`: in a `Full suite: CI` repo the CLAUDE.md `Quality check:` command runs; any other command still
  gives `not run (CI)`. Exit 0 with no runner summary there gives `passed (check only; CI runs the full suite)`;
  a non-zero exit fails as before.
- `review_loop_script.py`: `check_command_for` returns the `Quality check:` command in a CI repo.
- `handback.py`: the hand-back shows the check-only result on its `Full check:` line.
- `review-loop.md`: the check-only result routes like `not run (CI)`: run the changed files' tests.
- The changed-file tests still run, and `full_check_gate` still counts only `passed`, so a check-only pass leaves
  `untested_fix` set until the scoped tests pass.
- The opencode port has no full-check text, so it is not changed.

## Evidence

- A repo that forbids a local full test run names a compile-plus-format quality check. That check exits 0 with no
  runner summary. Before this change a `Full suite: CI` repo never ran its check (`not run (CI)`), so the /code gate
  never ran there, though the check is the repo's gate.

## Result

- The named test fails before (the check did not run: `not run (CI)`) and passes after. Also fail-first:
  `test_full_check.py::FullCheckTest::test_a_failing_declared_check_of_a_repo_whose_full_suite_runs_in_ci_fails`,
  `test_review_loop_script.py`'s `test_a_repo_whose_full_suite_runs_in_ci_converges_on_its_declared_check_with_no_tests`
  and `test_handback.py`'s did-not-run render test.

## Watch

—

## Back-out

Revert the commit.
