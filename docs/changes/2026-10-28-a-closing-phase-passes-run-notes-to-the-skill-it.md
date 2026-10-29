---
type: "Change"
title: "A closing phase passes run notes to the skill it invokes"
description: "`code_step.py start <plan> --phase <closing phase> <text>` now hands the text to the closing skill as run notes, and a resume keeps them, where it used to stop and start nothing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:01:40-05:00"}
seq: 211
kind: "fix"
components: ["script/code-step"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_run_notes_on_a_closing_phase_reach_the_skill_it_invokes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_start.py`: run notes on a closing phase no longer stop the start. The state saves them as `runNotes`,
  and the invoke-skill brief prints them under the same "Run notes from the user" heading a coder brief uses.
- `code_step.py`: a resume at a closing phase prints the saved run notes again.
- `start --help` says run notes go to the coder or, on a closing phase, to its skill.

## Evidence

- An orchestrator started a closing verify phase with run notes: a lower build-jobs limit, a ruling on a pending
  acceptance criterion, and a request to run the repo's non-negotiables check. `start` refused them and started
  nothing. The /code fork tried a flag `start` does not have, gave up after two dispatches, and the run fell back to
  the repo's default build-jobs count.
- Tests that fail on the base scripts and pass now:
  `test_code_step_start_input.py::StartInputTest::test_run_notes_on_a_closing_phase_reach_the_skill_it_invokes`,
  `test_code_step_resume.py::ResumeTest::test_resume_at_a_closing_phase_keeps_the_run_notes_it_started_with`.

## Result

- The notes reach the closing skill, so the fork has no refusal to guess its way around.

## Watch

- None: no intake counts closing-phase starts with run notes.

## Back-out

- Revert the commit.
