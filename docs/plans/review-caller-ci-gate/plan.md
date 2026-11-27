# Review caller CI gate: a caller ruling that CI is the test gate skips the local full check

A caller (a session ruling passed to /review, or /code's review step) can name a CI run as the test gate. The review
loop then runs lint but not the local full check, and the packet's `full_check` names the CI run. A repo-written
`Full suite: CI` rule is already honored by `review/full_check.py`; the caller flag goes through the same owner.

Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/full_check.py`, `review/full_check_gate.py`, `review/review_loop_prompt_file.py`,
  `review/review_loop_main.py`, `review/review_launch.py`, `code/code_review_start.py`, a usage-pointer line in
  `skills/review/SKILL.md` and `skills/code/SKILL.md`, and the tests of each.
- Out: the repo `Full suite: CI` reader (unchanged), `full_check.py main` (close-branch and verify callers),
  `capped_review.effective_status`.

## Phase Status

- [x] Phase 1: the `ci-gate` header skips the local full check and the packet names the CI run (risk: medium)

## Phase 1: the `ci-gate` header skips the local full check and the packet names the CI run

1. `full_check.py`: add the result prefix `NOT_RUN_CALLER_CI_PREFIX = "not run (CI gate: "` and
   `caller_ci_result(ci_run)`, which returns `not run (CI gate: <ci_run>)`. `run()` takes `ci_run=""`; when it is
   set, the run writes the started row and a finished row with `ci` true and `satisfied` true, runs no command, and
   returns that result. The result starts with `not run`, so `is_failure` is false and `handback.full_check_lines`
   shows it.
2. `review_loop_prompt_file.py`: add `CI_GATE_KEY = "ci-gate"` and its docstring line
   (`ci-gate: <CI run>  the caller's ruling that this CI run is the test gate: no local full check runs`).
3. `review_loop_main.build_loop`: `loop.ci_run = header.get(CI_GATE_KEY, "")`.
4. `full_check_gate.py`: `init_full_check_state` sets `self.ci_run = ""`; `run_full_check` passes `ci_run` to the
   runner when set; `run_check` passes `self.ci_run`. Lint still runs.
5. `review_launch.py`: `--ci-gate RUN` adds the `ci-gate: RUN` header pair. `code_review_start.py`: `--ci-gate RUN`
   adds the header line, and a detached run keeps the option for its child.
6. `skills/review/SKILL.md` flag list: `ci-gate=<run>` → `--ci-gate <run>`. `skills/code/SKILL.md` step 5: add
   `--ci-gate <run>` when the user ruled that a CI run is the test gate. Both lines are usage pointers.

#### Automated Verification

- [x] `tests/scripts/test_full_check.py`: `run(..., ci_run="gh run 123")` runs no command (a command that would fail),
  returns `not run (CI gate: gh run 123)`, and writes a satisfied receipt. Fails before the change (no `ci_run`).
- [x] `tests/scripts/test_review_launch.py`: `--ci-gate X` puts `ci-gate: X` in the header.
- [x] `tests/scripts/test_code_review_start.py`: `--ci-gate X` puts `ci-gate: X` in the dry-run prompt.
- [x] `tests/scripts/test_full_check_gate.py`: a loop step with `ci_run` set reports the CI-gate result and runs no check.
- [x] `python3 tests/parallel_tests.py` on the changed test files passes; `bash tests/lint.sh` on the changed .py files.
