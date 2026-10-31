---
type: "Change"
change_type: "fixed"
title: "A /code phase stays open when its review loop did not converge"
description: "code-step records how each review loop ended and, when it did not converge, leaves the phase open, commits nothing, records no reviewed-tree fingerprint and says what the run waits on."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T00:15:29-05:00"}
seq: 1
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment", "tests"]
watches: []
test: "tests/scripts/test_code_step_open_phase.py::PhaseStaysOpenWhenTheReviewDidNotConverge::test_a_loop_that_ended_on_a_plan_impact_question_marks_nothing_and_records_no_fingerprint"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `command_after_review` saves the packet status as `reviewStatus`; a new review dispatch clears it.
- `mark_review_gate_clean` (called first by `finish_phase`) stops when `reviewStatus` is anything but converged or deferred: stage `stopped`, no gate mark, no reviewed-tree fingerprint, and a stop line that says the phase stays open.

## Evidence

Judgment: a /code run marked a phase done and committed it after its review loop stopped on a plan-impact question with no fixes applied. The shared hand-back store is keyed by session and can hold an earlier converged hand-back, so it cannot overrule the packet the run read. Tests: `test_code_step_open_phase.py` (4 for this defect) failed on the unfixed script and pass now.

## Result

Not installed yet.

## Watch

None. A fix: tests prove it.

## Back-out

Revert `code_step.py` and `code_step_boundary.py` and delete the test file.
