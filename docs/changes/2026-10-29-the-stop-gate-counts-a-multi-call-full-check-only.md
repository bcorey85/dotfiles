---
type: "Change"
title: "The stop gate counts a multi-call full check only when each call passed"
description: "The stop gate counts a shell call of several full_check.py calls only when it printed one result line per call and each is passed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T00:00:00-05:00"}
seq: 267
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::ReviewLoopGateTest::test_a_command_of_two_full_check_calls_counts_only_when_each_call_printed_passed"
asked: ""
proof: []
unmeasured: ""
---

## Change

The stop gate read only the first `full check:` line of a shell call. A call that chained two `full_check.py` runs counted when the first passed and the second failed or printed nothing. It now counts such a call only when it printed one result line per `full_check.py` call and each one is `passed`.

## Evidence

Failing first: on master the new test failed (a two-call command counted on its first line).

## Result

The new test passes. Scoped modules pass; ruff is clean.

## Watch

—

## Back-out

Revert the commit.
