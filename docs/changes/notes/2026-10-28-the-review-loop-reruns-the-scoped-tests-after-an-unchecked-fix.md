---
type: "Change"
change_type: "fixed"
title: "The review loop reruns the scoped tests after a fix no full check verified"
description: "A converged review loop whose last coder pass no passed full check followed reruns the run's scoped test commands, reports the result as scoped_tests in the hand-back, and stops critical-blocker when one fails."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 189
kind: "fix"
components: ["script/review-loop-script", "script/coder-gate", "script/handback", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_scoped_test_left_red_by_the_last_fix_stops_the_loop"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_script.py`: after class closure, a converged loop with a coder pass that no passed full check came
  after runs the run state's `gateCommands` through `coder_gate.run_scoped_tests`. A failing command stops the loop
  `critical-blocker` with the failing tests' tail. The packet carries the one-line result as `scoped_tests`.
- `coder_gate.py`: `run_scoped_tests` runs the scoped commands as the gate does, outside a hook, and sorts setup
  faults, command errors and timeouts apart from real failures.
- `handback.py`: the full-check lines add "Scoped tests after the last fix: <result>".

## Evidence

- Queue items review-loop-reports-pass-without-rerunning-tests and review-loop-fix-leaves-a-scoped-test-red-and-the:
  the loop handed back a pass with a scoped test red from its last fix.
- The new tests fail on the old script: the packet has no `scoped_tests` and a red scoped test still converges.

## Result

- A hand-back after an unchecked fix says whether the scoped tests pass, and never converges over a red one.

## Watch

—

## Back-out

Revert the commit.
