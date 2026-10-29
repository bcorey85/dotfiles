---
type: "Change"
change_type: "fixed"
title: "A headless /code run commits and goes on where a phase waits for sign-off"
description: "`code_step.py start --headless` turns every block B sign-off stop into a block A commit and auto-advance, and carries the flag to each next phase and to a restart; the phase-end block text moves to code_step_phase_end.py."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T08:00:00-05:00"}
seq: 158
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_headless_run_commits_and_advances_where_a_phase_would_wait_for_sign_off"
asked: "2026-10-28: agent-evals-64 assigned queue item code-end-of-phase-stop-waits-for-a-person-in"
proof: []
unmeasured: ""
---

## Change

- `start --headless` saves `headless` in the run state. `boundary_decision` gives such a run block A wherever it gave
  block B (Phase 1 calibration, an exception, high risk). The block A line names the risk, with `, headless`.
- Block C (last phase, the only phase, a gated phase ahead), asks, plan-impact and blockers still stop.
- `carried_start_words` passes the modifier and `--headless` to the next phase's start and to a restart.
- The phase-end block text builders move from code_step_boundary.py (1001 lines) to the new code_step_phase_end.py.

## Evidence

- A worker run told never to prompt a person stopped at Phase 0's sign-off block; the parent session had to tell it to
  commit and resume, once per phase.
- The two new test_code_step.py tests fail on the old script.

## Result

- A headless run commits each phase by path and starts the next one on its own, up to the last phase.

## Watch

—

## Back-out

Revert the commit.
