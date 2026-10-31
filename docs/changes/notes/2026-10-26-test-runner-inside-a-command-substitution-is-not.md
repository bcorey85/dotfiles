---
type: "Change"
change_type: "fixed"
title: "Test runner inside a command substitution is not judged no-test-matched"
description: "A test runner inside $(...) or backticks is not judged no-test-matched, because the outer command's output does not carry its report."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T11:00:34-05:00"}
seq: 59
kind: "fix"
components: ["script/test-run-output", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_test_run_output.py::MatchesNoTestTest::test_a_runner_inside_a_command_substitution_is_not_judged"
asked: ""
proof: []
unmeasured: ""
---

## Change

matches_no_test in lib/test_run_output.py now strips command substitutions before looking for a test runner. A check such as `test "$(cargo test X -- --exact 2>&1 | rg -c ok)" = 2` prints nothing, so its passed count read 0 and the exit was rewritten to no-test-matched.

## Evidence

judgment: a peer session saw a passing count check fail this way. The new test fails on the base commit for the dollar and backtick forms and passes after.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Remove SUBSTITUTION and its use in matches_no_test, and the test.

