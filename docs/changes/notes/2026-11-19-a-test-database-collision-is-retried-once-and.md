---
type: "Change"
change_type: "fixed"
title: "a test database collision is retried once and never counted"
description: "A Django test-database collision in the hand-back gate or the full check is retried once; a pass on retry counts as a pass, and a second collision is a setup fault naming the collision and the fix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 4
kind: "fix"
components: ["script/check-output", "script/coder-gate", "script/full-check"]
evidence: ["review-loop-test-db-collides-across-worktrees", "hand-back-gate-reads-a-shared-test-db-collision-as"]
watches: []
test: "tests/scripts/test_coder_gate.py::RunCommandsTests::test_a_second_collision_is_a_setup_fault_naming_the_fix_and_no_real_failure"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/check_output.py` reads the known collision shapes; `lib/collision_retry.py` owns the single retry, its wait and
the retry decision. `code/coder_gate.py` and
`review/full_check.py` retry a collided failing run once when time is left; a second collision is a setup fault, never
a counted attempt or a blocker.

## Evidence

Two worktrees ran the same test database name at once, and the gate counted the collision as a failed attempt.

## Result

`test_check_output.py` TestDbCollisionTest; `test_collision_retry.py` CollisionRetrySecondsTest; new tests in `test_coder_gate.py` and
`test_full_check.py`.

## Watch

None.

## Back-out

Revert the commit.
