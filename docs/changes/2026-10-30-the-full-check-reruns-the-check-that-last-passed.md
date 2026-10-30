---
type: "Change"
change_type: "fixed"
title: "the full check reruns the check that last passed and fails a run of no test"
description: "In a repo with no `Quality check:` line, the review loop reruns the full check that last passed there instead of asking the check finder again, and a check that ran no test is a setup fault that names the line to add, even at exit 0."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T06:01:47-05:00"}
seq: 310
kind: "fix"
components: ["script/full-check", "script/check-output", "script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_discover_that_finds_no_test_in_a_subfolder_repo_names_the_quality_check_fix"
asked: ""
proof: []
unmeasured: "Two loops on one repo showed it; no intake row counts which command a check finder picked or how many tests a full check ran."
---

## Change

In a repo whose CLAUDE.md names no `Quality check:` line, `full_check.main` and `FullCheckSteps.run_check` keep the uncut command of each `passed` check, before any `Expected red` step is left out, in `full-check-last-passed` under the git common dir, so every worktree of the repo shares it. `full_check.picked_check_command` returns the `Quality check:` command, else that saved one. `review_loop_script.check_command_for` takes it before it calls the haiku check finder, so the scripted loop picks the same check every run once one has passed.

`full_check.py` run with no `-- '<command>'` picks the same way. With neither a `Quality check:` line nor a saved check it prints `full check: setup fault (no Quality check line, and no full check has passed here)` and a `fix:` line, and exits 1. Step 6 of `review-loop.md`, and its opencode port, now run the script with no command and tell the agent never to pick one; a scoped or unresolved pick returns `setup-fault`. On the no-pick setup fault the agent sets `not run (no check found; the coder's scoped tests stand)` and goes on, as it did before, so a /review on a repo with no `Quality check:` line does not stop. A check that runs 0 tests still fails, and the fallback never reads as a pass.

A check that exits 0 but ran no test (`Ran 0 tests`, `NO TESTS RAN`, jest's `Tests: 0 total` or `No tests found, exiting with code 0`), with no other runner summary that shows tests ran, is now `setup fault (exit 0)`. Before, jest's line read `passed` and the others `unverified`. `check_output.ran_no_test` holds the no-test rule for both exit paths. For a no-test setup fault in a repo with no `Quality check:` line, the log tail printed under the result opens with `fix: the check ran no test; add a Quality check: \`<command>\` line to <repo>/CLAUDE.md`, naming the command that last passed there when one did and is not the command that ran.

## Evidence

Two /review loops ran on a repo whose tests sit in `bin/` and whose CLAUDE.md names no check. The check finder gave one loop `cd bin && python3 -m unittest discover -p "test_*.py"` (1256 tests OK) and the other `python3 -m unittest discover` from the root: 0 tests, a generic setup fault, a stop, and a dirty gate.

## Result

The subfolder test fails against the previous script: its root discover prints a setup fault with no fix line. The exit-0 test fails on all three no-test outputs (one `passed`, two `unverified`). The review-loop test fails because the second run calls the check finder again. The no-command test fails because the previous script requires `--`, the cut-step test because the fix line named the saved command that had just run, and the guidance test because Step 6 passed `-- '<command>'`. All pass with the change; a chained check whose other step ran tests still passes.

## Watch

None: no intake number reads the full check's command or its test count.

## Back-out

Remove `last_passed_path`, `last_passed_command`, `picked_check_command`, `remember_passed_command`, `no_test_fix_lines`, the no-command branch of `main` and their constants from `full_check.py`, and `remember_as` from `full_check_gate.py` and `review_loop_script.py`; restore Step 6 of both `review-loop.md` files; the exit-0 no-test branch and the fix line in `failed_run_result`; remove `NO_TESTS_EXIT_ZERO` and `ran_no_test` from `check_output.py` (restore the inline test in `is_setup_fault`); remove the last-passed lookup from `check_command_for`; restore the placeholder text in `code_step_review_stops.unverified_check_why_and_fix`; and remove the thirteen tests.
