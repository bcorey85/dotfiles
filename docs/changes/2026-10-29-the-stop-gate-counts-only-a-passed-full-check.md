---
type: "Change"
title: "The stop gate counts only a passed full check result"
description: "The review-loop stop gate reads full_check.py's result line instead of the command text, so a failed, unverified or bare-runner check no longer lets the loop stop, and full_check.py refuses a command scoped to files or tests."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T08:46:35-05:00"}
seq: 246
kind: "fix"
components: ["script/review-loop-gate", "script/full-check", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::ReviewLoopGateTest::test_a_full_check_script_call_whose_result_is_not_passed_is_blocked"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_gate.py`: a Bash call counts as the full check only when it ran `full_check.py` and its own result
  (matched by tool_use_id) opens with the line `full check: passed` (the first `full check:` line only). The gate reason says no passed
  `full_check.py` result follows the last code change, and routes a non-passed result through Step 6. The command-text regexes that judged checkers and
  scope (`CHECKER`, `SCOPED`, `NON_SCOPING_FLAGS`, `GATE_LOG`, `REDIRECT`, `scoping_words`, `full_check`) are gone.
- `full_check.py`: the CLI (`main()`, not `run()`) refuses a command that `check_scope.command_check_scope` scores as
  targeted, with `full check: not run (scoped command: ...)`, unless the command equals the CLAUDE.md
  `Quality check:` command. In a `Full suite: CI` repo it prints `not run (CI)` for any command. Scope is judged in `check_scope` only, the module the coder gate reads.
- `review-loop.md` Step 6: on the scoped result, run the CLAUDE.md quality-check command as written.
- `script_utils.strip_flag_values` and its tests are deleted (no production caller).

## Evidence

- The stop gate judged the full check from the command text with its own regex set, apart from the coder gate's
  `check_scope`. It let the loop stop after a check whose result was failed or unverified, and after a bare
  `npm test` that never went through `full_check.py`.

## Result

- The named test fails before (the stop is allowed after a failed, unverified, setup-fault, timeout or
  pre-existing-failure result) and passes after. Also fail-first:
  `test_review_loop_gate.py::ReviewLoopGateTest::test_a_bare_checker_command_with_a_passing_looking_output_is_blocked`
  and `test_full_check.py::FullCheckTest::test_a_command_scoped_to_files_or_tests_is_not_run_and_a_whole_suite_command_is`.
- `full_check.py` refuses only a targeted command, not one `runs_whole_check` reports as not whole: that reading
  scores `cargo test`, `make check` and `bash tests/run.sh` as not whole, and they are real full checks.

## Watch

—

## Back-out

Revert the commit.
