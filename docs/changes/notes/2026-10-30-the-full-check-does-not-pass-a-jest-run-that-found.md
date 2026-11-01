---
type: "Change"
change_type: "fixed"
title: "the full check does not pass a jest run that found no test"
description: "A jest run that exits 0 after finding no test now reads as a run of no test, so the full check reports it unverified instead of passed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T15:42:28-05:00"}
seq: 401
kind: "fix"
components: ["script/check-output"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_check_output.py::CheckVerdictTest::test_check_verdict_and_every_pass_rule_agree_on_each_command_and_output"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_output.NO_TESTS_EXIT_ZERO` matches jest's no-test lines. `check_verdict` and `ran_no_test` read an exit-0 run with that line as a run of no test.

## Evidence

`jest --passWithNoTests` and a filter that matches nothing exit 0 and print no runner summary of passed tests.

## Result

The two new jest rows in `test_check_output.py` pass.

## Watch

—

## Back-out

Delete `NO_TESTS_EXIT_ZERO` and its two uses.
