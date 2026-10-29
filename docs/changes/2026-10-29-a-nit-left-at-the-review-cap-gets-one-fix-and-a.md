---
type: "Change"
title: "A blocker left over at the review cap still blocks the commit"
description: "The review hand-back hook refuses a converged or deferred packet whose leftovers hold a blocker, or whose full check failed or hit a setup fault, so neither can clear the commit gate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T10:33:12-05:00"}
seq: 253
kind: "fix"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_handback.py::ReviewerRequiredTest::test_a_nit_fixed_at_the_cap_exit_commits_and_a_blocker_left_over_does_not"
asked: ""
proof: []
unmeasured: ""
---

## Change

`handback.py`: `status_problems` refuses a `converged` or `deferred` packet whose `findings_remaining` holds a blocker,
so the hand-back hook denies it and the commit gate stays shut. It also refuses a clean status whose `full_check`
failed or hit a setup fault; `test_a_clean_status_with_a_failed_full_check_is_refused` covers it beside the blocker
test. `review-loop.md` gives `findings_remaining` entries a `blocker` field and says a blocker never leaves on
`deferred` or `converged`.

The cap exit's scoped reviewer still sends every fix finding to `findings_remaining` with `cap-reached`. A route where
one coder fixes nit or wording leftovers there and the loop converges was drafted and taken out: it is a prompt change
with no bench finding, so it has no kind that ships.

## Evidence

A blocker left in `findings_remaining` on a `deferred` packet was accepted, and the gate earned clean credit.

## Result

The new test failed before the change (a deferred packet with a blocker leftover was accepted) and passes after it. In
the same test, a converged packet whose last step is a coder is still accepted.

## Watch

None; a fix with a test.

## Back-out

Revert the `status_problems` checks in `handback.py`, the `blocker` field lines in `review-loop.md` and the two tests.
