---
type: "Change"
change_type: "fixed"
title: "Code phase verification fails a filtered test run that matches no test"
description: "code_step_boundary.run_verification_commands marks a filtered test command that exits 0 and reports no passed test as failed, with the zero-test check criteria_dry_run.py already used, now shared from lib/test_run_output.py; mocha and bun summaries now count as passed tests."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T08:33:10-05:00"}
seq: 47
kind: "fix"
components: ["script/code-step", "script/criteria-dry-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_filtered_test_run_that_matches_no_test_fails_the_verification"
asked: ""
proof: []
unmeasured: ""
---

## Change

`run_verification_commands` in `code_step_boundary.py` judged each phase verification command by its exit code alone. A vitest, jest or cargo filter that matches no test exits 0, so a phase's verification box passed with no test run. The command now counts as failed (exit 1, plus a note that the filter matched no test) when it is a test runner command with a test filter, exits 0, and its output reports no passed test. `run_phase_verification` already stops on any failed command, so the phase stops there.

The check moves out of `tools/criteria_dry_run.py` into `lib/test_run_output.py`, and both scripts import it. The passed-test count now also reads mocha's `N passing` and bun's `N pass`. Before, a filtered mocha or bun run that passed counted as a zero-test match, which would have stopped `/code` on a green run and marked the eng-spec dry run RED.

## Evidence

judgment: the eng-spec dry run already marks a zero-test match RED, and `/code` phase verification did not, so the same plan check passed in one place and failed in the other. `test_a_filtered_test_run_that_matches_no_test_fails_the_verification` fails on the base commit (the command reports exit 0) and passes after. `test_a_filtered_test_run_that_reports_a_passed_test_stays_green` passes in both. `tests/scripts/test_test_run_output.py` covers each runner's summary line, including the mocha and bun ones that read as zero before.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Remove the `matches_no_test` branch in `run_verification_commands` and the two tests in `test_code_step.py`. To restore the old layout too, move the definitions in `lib/test_run_output.py` back into `criteria_dry_run.py` and drop `test_test_run_output.py` and the staging-list entries.
