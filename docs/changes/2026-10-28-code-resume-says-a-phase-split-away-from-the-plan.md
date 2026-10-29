---
type: "Change"
title: "code resume says a phase split away from the plan is stale at a plan-fix stop"
description: "A stop for a verification or plan-format fix no longer hides that the stopped phase id left the plan."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T14:10:00-05:00"}
seq: 199
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_resume_at_a_stop_whose_phase_was_split_away_says_the_phase_left_the_plan"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The stale-phase check skips a phase's text edit at a plan-fix stop, as before, but reports a phase id that is gone from the plan there. An unreadable plan file at such a stop still goes on to the stop, as before.

## Evidence

- After a plan split a stopped phase, resume replayed the old stop question with the old phase text instead of saying to restart on the new phase.
- The new test fails on the old script for both plan-fix stop reasons.
- Regression tests added for `start --restart --phase <id> <run notes>` (unspaced, stopped and one-quoted-argument forms) passed before the change, so that half of the report was already fixed on this base.

## Result

- Resume at such a stop offers the restart on the plan's next open phase.

## Watch

—

## Back-out

Revert the commit.
