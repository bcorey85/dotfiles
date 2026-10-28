---
type: "Change"
title: "A verify-only ask whose checks pass with no edit finishes the phase"
description: "An asks coder's ALREADY-DONE line may name a backticked command that exited 0, so a verify-only ask whose checks pass with no edit goes on to the end-of-review gate and commit; a report with no such line still stops."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:40:00-05:00"}
seq: 133
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_asks_coder_already_done_line_naming_a_passing_check_finishes_the_phase"
asked: "2026-10-27: agent-evals-64 assigned queue item a-verify-only-ask-that-changes-no-files-stops-the (rank 228)"
proof: []
unmeasured: ""
---

## Change

- `code_step_report.already_done_ask_numbers`: an `ALREADY-DONE: <n> — `<command>` -> exit 0` line counts, as a
  `file:line` line does. Any other exit, or text after `exit 0`, does not count.
- The asks-coder prompt names that form for an ask that only asks for checks to run.
- The finish text says the coder named where each ask is in the code or the check that passed.

## Evidence

- A /code run's accepted ask asked the coder only to run tests. They passed with no edit, and `code_step.py` stopped
  on "no reviewable change", so the phase needed a manual `tick`.
- The new passing-check test fails on the old scripts. The failing-check and trailing-text tests pass on both.

## Result

- A verify-only ask with passing checks runs the phase's Automated Verification, marks the gate and commits. A stall
  still stops.

## Watch

—

## Back-out

Revert the commit.
