---
type: "Change"
title: "A code phase stops when its full check shows no test run"
description: "A /code phase whose review converged with the full check unverified (exit 0, no runner summary) finished as if verified, although the check did not show that any test ran. The phase now stops with the reason check-unverified, names the check command, and asks for a fix before review-again: a Quality check line in the repo's CLAUDE.md when it has none, else a check that prints its runner summary or a SUMMARY_LINES entry for the runner's format."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T06:34:11-05:00"}
seq: 235
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_converged_review_whose_full_check_ran_no_tests_stops_the_phase_and_asks_for_a_quality_check_line"
asked: ""
proof: []
unmeasured: "The change adds a stop on a rare packet state; no intake number reads it."
---

## Change

- `code_step_review.stop_on_review_status` stops a converged or deferred review packet whose `full_check` is unverified (`full_check.is_unverified`). The state becomes stage `stopped` with stop reason `check-unverified`. The question says the full check exited 0 and printed no test-runner summary, so the check did not show that any test ran, names `full_check_command`, and tells the caller to fix the check, run review-again, and not mark the phase done. With no `Quality check:` line in the repo's CLAUDE.md, the fix is to add one. With a line, the fix is below. The reviewer's asks print with the stop.
- `review-again` accepts a stopped state with the stop reason `check-unverified`.
- When the repo's CLAUDE.md already holds a `Quality check:` line (the pattern is now `full_check.QUALITY_CHECK_LINE`, shared with the review loop), the `check-unverified` stop says the configured check printed no test-runner summary this toolkit recognizes, names the command, and says to make the check print its runner's summary or add the format to `SUMMARY_LINES` in `lib/test_run_output.py`, then run review-again.

## Evidence

- A /code phase run finished with the packet's full check "unverified (exit 0, no runner summary)". The repo's CLAUDE.md had no `Quality check:` line, so the check finder named only the gate steps that run no tests. The suite never ran.
- The new test fails before the change: the phase did not stop, and review-again was refused.

## Result

- The new tests pass. The hand-back tests pass, and ruff is clean on the changed files.

## Watch

—

## Back-out

Revert the commit. A converged review with an unverified full check then finishes the phase again.
