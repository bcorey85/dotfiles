---
type: "Change"
change_type: "fixed"
title: "Setup-fault and critical-blocker hand-backs skip the full-check gate"
description: "A review loop that stops with setup-fault or critical-blocker no longer gets denied for a missing full check, whether or not a coder step came before, because those statuses claim no verified tree, like plan-impact."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T04:13:13-05:00"}
seq: 320
kind: "fix"
components: ["script/handback", "script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_hand_back_that_dispatched_no_reviewer_and_logged_only_a_not_dispatched_metrics_line_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/loop_transcript.py` names the statuses that stop the loop without claiming the tree is verified
  (`plan-impact`, `setup-fault`, `critical-blocker`) in one frozenset, and `scan()` exempts a hand-back with any of
  them from the full-check gate. Before, only `plan-impact` was exempt. The hand-back hook and the stop hook both
  read the rule through `scan()`, so both follow it.
- The defaults for the last code step and last full check do not change: a loop that ran no coder still owes a full
  check before a converged, deferred or cap-reached hand-back. A new test pins that a converged hand-back with no
  coder step and no full check is denied.

## Evidence

A loop that stopped on a setup fault or a critical blocker before any coder ran was denied once with "No passed
full_check.py result follows the last code change in this phase", though it never claimed a verified tree. The early
exit test failed on those two cases and now passes with the converged and plan-impact cases.

## Result

The hand-back, review-loop-gate and review-loop script tests pass (406 tests).

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
