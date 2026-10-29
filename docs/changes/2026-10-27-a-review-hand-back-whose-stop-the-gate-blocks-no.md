---
type: "Change"
change_type: "fixed"
title: "A /code phase is marked done only after the review loop is allowed to stop"
description: "code_step counts a review-loop agent's hand-back only once the review-loop gate lets the loop stop after it, so `resume` no longer marks a phase done on a hand-back the gate then sent back to work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:30:22-05:00"}
seq: 130
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_hand_back_whose_stop_the_gate_blocked_leaves_the_phase_open"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_core.awaited_handback` returns a review-loop agent's hand-back only after the review-loop gate wrote an
  unblocked stop row for that agent at or after it. A blocked stop row means the loop went back to work, so the wait
  goes on for its next hand-back. Only the hand-back wait waits for the stop row, up to 15 s. With no stop row by then,
  or when the wait ends first, the hand-back counts as before. Every other reader counts a hand-back with no stop row.
- Coders and the review-loop script are not affected: they stop with no gate.
- A verb that finds only a hand-back with a blocked stop prints `ACTION: wait` and says to run `resume` again. Before,
  it took that packet.
- `handback.stop_rows_after` is the one reader of a loop's stop rows after a time. `settled_stop_row` now uses it.

## Evidence

- A /code fork saw `Phase 3 marked done` before the review-loop's hand-back arrived, and the review converged later.
  The repro: the log-hook writes the hand-back event at the SubagentHandback PostToolUse. The review-loop gate can
  block the SubagentStop that follows. `resume` took the first packet at once and marked the phase done while the loop
  kept working.
- Three new tests fail on the old scripts: a blocked stop leaves the phase open, the hand-back after it marks the phase
  done with the later packet, and a timed `resume` waits out a block that lands after the hand-back.

## Result

- No `resume` marks a phase done while the review-loop it waits on is still working.

## Watch

—

## Back-out

Revert the commit.
