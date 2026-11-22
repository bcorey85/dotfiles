---
type: "Change"
change_type: "fixed"
title: "A recorded acceptance clears a known pre-existing scoped failure"
description: "accepted_failures.py records a user's acceptance of a failing line, and the full-check gate reads that line as pre-existing when the base run fails it too."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 33
kind: "fix"
components: ["script/accepted-failures", "script/full-check-gate", "script/check-output"]
evidence: ["review-loop-cannot-accept-known-pre-existing"]
watches: []
test: "tests/scripts/test_full_check_gate.py::AcceptedScopedFailureTest::test_a_changed_throttling_line_is_pre_existing_with_a_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `review/accepted_failures.py` with `accept` and `list`. `full_check_gate.scoped_failures_pre_existing` counts an accepted line that also fails at base as pre-existing, and lines that differ only in numbers do not count as new. The scoped-failure blocker prints the `accept` command.

## Evidence

Scoped tests failed at HEAD and on the branch with differing 429 lines, so the loop read them as new, ended critical-blocker, and no verb cleared it.

## Result

AcceptedScopedFailureTest, RedScopedRunStopTest and AcceptedFailuresCliTest in `test_full_check_gate.py`.

## Watch

None.

## Back-out

Revert the commit.
