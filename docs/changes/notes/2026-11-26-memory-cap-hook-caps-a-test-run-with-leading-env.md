---
type: "Change"
change_type: "fixed"
title: "memory-cap hook caps a test run with leading env assignments"
description: "The memory-cap hook now puts the cap after leading NAME=value words and allows the call, instead of denying it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T12:00:56-06:00"}
seq: 17
kind: "fix"
components: ["script/memory-cap-scope", "script/inline-interpreter-hint"]
evidence: ["tests/scripts/test_memory_cap_scope.py::HookTest.test_a_test_step_with_leading_assignments_gets_the_prefix_after_them"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::HookTest.test_a_test_step_with_leading_assignments_gets_the_prefix_after_them"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

A single test command with leading literal NAME=value words, such as `PYTHONPATH=tests/scripts python3 tests/parallel_tests.py x.py`, now comes back with the cap inserted after the assignments and before the program, and is allowed. Before, the hook denied it. An already-capped form with assignments stays unchanged. A value with a `$`, backtick, backslash, `~` or unquoted shell operator is still denied, and so is an assignment to PATH (or zsh's `path`); a quoted literal value is kept in front of the cap.

## Evidence

HookTest.test_a_test_step_with_leading_assignments_gets_the_prefix_after_them in tests/scripts/test_memory_cap_scope.py fails before the change (deny) and passes after. On the rewrite path (an env-assignment test command, rewritten and allowed) the hook takes a median of 40.1 ms per call (15 runs) beside 7.8 ms for a bare python start.

## Result

The verify payload's first test call is allowed with the cap in place, with no deny and resend.

## Watch

—

## Back-out

Revert memory_cap_scope.py and the tests.
