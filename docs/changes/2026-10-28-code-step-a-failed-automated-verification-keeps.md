---
type: "Change"
change_type: "fixed"
title: "code-step: a failed Automated Verification keeps the failing test names"
description: "An Automated Verification stop now lists the failing-test lines of the whole output above the last 400 characters. Before, it showed only those last 400 characters of a failed command, so the failing test names were lost."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:51:07-05:00"}
seq: 183
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_failed_verification_keeps_the_failing_test_names_above_the_tail"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The verification stop prints `Failing tests:` and the failing-test lines of the whole output above the 400-character
  tail, through the shared `tail_with_failing_tests`.
- `finish_phase` takes the result of a passing verification run the caller already made, so a restart does not run the
  checks twice.

## Evidence

- A /code run stopped on an integration test file that failed 2 of 14. The hand-back held only the tail of the output
  and named no failing test.

## Result

- The hand-back names the tests that failed.

## Watch

—

## Back-out

Revert the commit.
