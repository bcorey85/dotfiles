---
type: "Change"
change_type: "fixed"
title: "the check-unverified stop names the Full suite CI line for a check the toolkit does not recognize as a test run"
description: "When a repo's configured check is not a command the toolkit recognizes as a test run, the /code check-unverified stop names the `Full suite: CI` line and the SUMMARY_LINES fix, so a CI-gated repo is fixed once instead of needing a ruling at every phase."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T19:08:50-05:00"}
seq: 289
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_an_unverified_stop_for_an_unrecognized_check_names_the_full_suite_ci_line_and_summary_lines"
asked: ""
proof: []
unmeasured: ""
---

## Change

The check-unverified stop in `code_step_review_stops.py` reads the repo's configured `Quality check:` command with `test_run_output.runs_tests`. When that command is not recognized as a test command, the stop says so and names two fixes: add the `Full suite: CI` line to the repo's CLAUDE.md if CI runs the full suite, or make the check print a runner summary or extend SUMMARY_LINES. The full check then accepts the declared check as check-only. A configured check that runs tests keeps the old advice: print the runner's summary or extend SUMMARY_LINES. CLAUDE.md prose is not matched.

## Evidence

judgment: a work session hit this stop at every phase in a repo whose check ran only fmt and a type check, and the stop's advice never named the line that fixes it.

## Result

A repo whose check is `cargo fmt --check && cargo check` gets a stop that names both `Full suite: CI` and SUMMARY_LINES. A check that runs tests keeps the summary advice.

## Watch

None.

## Back-out

Revert this change's commit.
