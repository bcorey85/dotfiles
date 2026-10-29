---
type: "Change"
change_type: "fixed"
title: "review gate runs the listed scoped tests and keeps the full output"
description: "A plan that listed its tests behind wrappers (`nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run ...`) got a gate of derived `cargo clippy` and `cargo test --tests`, every target in the crate: the test-word list lacked `nextest` and the cargo check did not peel the wrappers. The review loop's scoped-test step also kept only an output tail with no cargo or nextest failure lines, so the packet could not name the failing test. The gate now takes the listed commands behind env, nice, timeout and taskset, `nextest` counts as a test run, the full output goes to scoped-tests.log in the loop's script folder, and the packet names each failing test and the log while the blocker quotes each test's error text, panic messages included. A panic line compares equal across runs whatever its thread id, line and column. /code's fork brief also says every report goes back through the hand-back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T12:00:00-05:00"}
seq: 232
kind: "fix"
components: ["script/code-step-gates", "script/coder-gate", "script/review-loop-script", "script/check-output", "script/full-check", "script/shell-command", "script/test-run-output", "skill/code", "agent/review-loop"]
evidence: ["session-report"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_red_scoped_test_names_the_failing_test_and_its_panic_text_and_keeps_the_full_output"
asked: ""
proof: []
unmeasured: "A gate widening shows only as a review run's wall time and its test command list; no telemetry row records which gate commands a phase got against the ones its plan listed."
---

## Change

- `test_run_output.TEST_WORD` takes `nextest`, so `cargo nextest run` is a test run.
- `code_step_gates.runs_cargo` replaces the `RUNS_CARGO` regex. It reads the command's steps through `shell_command.resolved_command_words` (moved there from `review_commit_gate`, with `LINE_CONTINUATION`), which peels each step's wrappers and strips line continuations, so `cargo \<newline> test` counts as cargo. Text the splitter cannot read is not cargo.
- `shell_command`: `taskset` is a wrapper whose first value (the CPU mask or list) is dropped, like `timeout`'s duration.
- `check_output.FAILING_TEST_LINE` matches cargo's `test x ... FAILED` and the `thread '...' panicked at` line, so a panic's message lines are its failing block's error text. `normalized_log_line` drops a panic line's thread id and `:LINE:COL` and keeps its file path. `RUST_FRAME_LINE` marks the lines cargo and nextest print around a panic (`running N tests`, passing tests, `failures:`, the test-name list, `---- x stdout ----`, the backtrace note, `test result:`, `error: test failed`, nextest PASS, rule, `stdout ───`, Summary and `Cancelling due to test failure` lines) as not error text, so a failing block's last lines hold the assertion values (`left: 3`, `right: 4`). The frame lines are dropped only in a block that starts with a panic line or a Rust failed-test header. `failing_test_quote` accepts a Rust `... FAILED` or `FAIL [` header without error text of its own and lists it after the errors.
- `full_check`: a cargo or nextest full-check log now yields failing lines and failing blocks, and a panic that only moved lines still compares as the same failure.
- `script_utils.write_command_outputs` writes each command's whole output to one file. `code_step_boundary.save_verification_output` and the scoped-test step both use it.
- `coder_gate.run_scoped_tests` takes a log path. It writes the full output of each failing or timed-out command there. A failed result reads `failed: <cmds>[; failing tests: <lines>]; full output: <path>`; a setup-fault, command-error or timeout result ends with `; full output: <path>`. Each failure tail quotes the failing tests' error text through `failing_test_quote` and ends with the log path.
- `review_loop_script`: the scoped-test step writes `scoped-tests.log` in its `loop-script/<agent id>` folder.
- `review-loop.md`: the `scoped_tests` packet field lists the failing tests and the log path.
- `/code` rule 6: a fork sends no question or report by message, even when its task names a session to report to; both go back through the hand-back.
- Closes the queue item review-loop-runs-every-test-target-and-keeps-only.

## Evidence

- A session report: a phase that listed three `nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run ... -E 'test(...)'` commands got a gate of `cargo clippy` and `cargo test --tests`, the full target set the repo's CLAUDE.md forbids. The red result kept only a tail, so the failing test could not be named.
- Each new test failed on the base commit 9fdfb233: 5 in shell_command, test_run_output and check_output, the wrapper test in code_step, both scoped-test tests in review_loop_script, and the /code fork-rule test.
- A sweep of 7345 real plans parses all 7345. Of 31375 listed commands that name cargo, 31349 read as cargo; the distinct misses run cargo inside `sh -c` or `$(...)` as a check, or cannot be split.

## Result

- After the merge of origin/master, `bash tests/run.sh` passes: 3913 tests, 0 failed, ruff clean.

## Watch

—

## Back-out

Revert the commit. Wrapped listed commands then fall back to the derived cargo gate, and a red scoped test reports only its command and a tail.
