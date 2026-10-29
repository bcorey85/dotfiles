---
type: "Change"
title: "review gate runs the listed scoped tests and keeps the full output"
description: "A plan that listed its tests behind wrappers (`nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run ...`) got a gate of derived `cargo clippy` and `cargo test --tests`, every target in the crate, because neither the test-word list nor the cargo check peeled the wrappers. The review loop's scoped-test step also kept only an output tail with no cargo or nextest failure lines, so the packet could not name the failing test. The gate now takes the listed commands behind env, nice, timeout and taskset, `nextest` counts as a test run, the full output goes to scoped-tests.log in the loop's script folder, and the packet and blocker quote each failing test's name with its panic text and the log path. /code's fork brief also says every report goes back through the hand-back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T12:00:00-05:00"}
seq: 219
kind: "fix"
components: ["script/code-step-gates", "script/coder-gate", "script/review-loop-script", "script/check-output", "script/shell-command", "script/test-run-output", "skill/code", "agent/review-loop"]
evidence: ["session-report"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_red_scoped_test_names_the_failing_test_and_its_panic_text_and_keeps_the_full_output"
asked: ""
proof: []
unmeasured: "A gate widening shows only as a review run's wall time and its test command list; no telemetry row records which gate commands a phase got against the ones its plan listed."
---

## Change

- `test_run_output.TEST_WORD` takes `nextest`, so `cargo nextest run` is a test run.
- `code_step_gates.runs_cargo` replaces the `RUNS_CARGO` regex. It splits the command into steps and peels each step's wrappers with `shell_command.command_after_wrappers`. Text the splitter cannot read is judged by its first word.
- `shell_command`: `taskset` is a wrapper whose first value (the CPU mask or list) is dropped, like `timeout`'s duration.
- `check_output.FAILING_TEST_LINE` matches cargo's `test x ... FAILED` and the `thread '...' panicked at` line. `failing_test_lines` joins a panic line with up to six lines of its message. A panic line's thread id is dropped before two runs are compared.
- `coder_gate.run_scoped_tests` takes a log path. On a failure or timeout it writes every command's full output there. The result reads `failed: <cmds>; failing tests: <lines>; full output: <path>`, and each failure tail ends with the log path.
- `review_loop_script`: the scoped-test step writes `scoped-tests.log` in its `loop-script/<agent id>` folder.
- `review-loop.md`: the `scoped_tests` packet field lists the failing tests and the log path.
- `/code` rule 6: a fork sends no question or report by message, even when its task names a session to report to; both go back through the hand-back.
- Closes the queue item review-loop-runs-every-test-target-and-keeps-only.

## Evidence

- A session report: a phase that listed three `nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run ... -E 'test(...)'` commands got a gate of `cargo clippy` and `cargo test --tests`, the full target set the repo's CLAUDE.md forbids. The red result kept only a tail, so the failing test could not be named.
- Each new test fails on the base commit 9fdfb233: 5 in shell_command, test_run_output and check_output, the wrapper test in code_step, and both scoped-test tests in review_loop_script.
- A sweep of 7345 real plans parses all 7345. Of 31375 listed commands that name cargo, 31349 now read as cargo; the 3 distinct misses run cargo inside `sh -c` or `$(...)` as a check.

## Result

- The changed test files pass, ruff is clean, and the duplicate-code check passes. `bash tests/run.sh` ran 3857 tests with 1 failure: the /code fork-rule test pinned rule 6's old text. It now pins the new text, fails on the base and passes; test_code_step passes in full.

## Watch

—

## Back-out

Revert the commit. Wrapped listed commands then fall back to the derived cargo gate, and a red scoped test reports only its command and a tail.
