---
type: "Change"
change_type: "fixed"
title: "Failed verification saves its full output and quotes each test error"
description: "When /code's Automated Verification fails, the stop now writes the full output of each failed command to verification-output.txt in the run folder, names that path, and quotes each failing test's error text, bounded, or the output's tail when some failing test has no error text after it. Before, the stop report kept only the failing test names and the last 400 characters, so the panic text and assertion diffs were lost and a later /debug could not see the original failure."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T21:11:08-05:00"}
seq: 221
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_failed_verification_saves_full_output_and_quotes_the_error"
asked: ""
proof: []
unmeasured: "The change adds a file and report text on a stop; no intake number reads it."
---

## Change

- `code_step_boundary.stop_for_failed_commands` saves the full output of every failed command to `verification-output.txt` in the run folder (found with `run_file_path` and the state's `runId`; a run id is made when the state has none). The stop report names the path.
- Each failed command's quote is now the error text of each failing test (`check_output.failing_test_errors`): the failing line and the lines after it, leaving out runner summary lines, jest `PASS` lines, per-run clock lines, vitest check-mark lines, rule lines of `⎯` (bare or labeled, such as `⎯⎯ Failed Tests 2 ⎯⎯`), dashes and equals signs, and the unittest and Django run footer (`Ran N tests in …`, `FAILED (…)`, `OK`, test-database creation and teardown lines). A test with more than 6 lines after its failing line keeps the first of them and the last 5; a jest file with several `●` tests gets that bound for each test. The quote holds at most 40 lines of error text, then the names of any failing tests the cap cut, then a pointer to the full output in the file. The quote is used only when every failing test line has error text after it; otherwise (pytest prints the error text before its `FAILED` summary lines) the quote is the output's tail with the failing-test names, as before.
- `FAILING_TEST_LINE` no longer matches unittest's final `FAILED (…)` result line, which is not a test. This also changes `coder_gate` and `full_check`, which read it through `failing_test_lines` and `failing_block_details`.

## Evidence

- A failing verification command's output was cut to its names and 400 characters in the stop report; the original failure was not kept anywhere a later `/debug` could read.
- The new test fails before the change: the output file did not exist.

## Result

- The new test passes. The code-step and check-output tests pass, and ruff is clean on the changed files.

## Watch

—

## Back-out

Revert the commit. The stop report then quotes the names and the last 400 characters again, and no output file is written.
