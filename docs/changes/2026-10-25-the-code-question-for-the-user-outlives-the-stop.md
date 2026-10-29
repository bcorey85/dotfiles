---
type: "Change"
change_type: "fixed"
title: "The /code question for the user outlives the Stop hook, and resume takes the user's answer"
description: "code_step.py writes every ask-user question to question.md, which the Stop say-hook never empties, and `resume <answer>` at a stopped coder puts the answer in that question instead of refusing it, so a /code run that stops for the user no longer hands back an empty question."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T20:42:28-05:00"}
seq: 19
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_the_question_for_a_stopped_coder_outlives_the_main_sessions_stop_hook"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step_core.py`: `ask_user` writes the question to `<git dir>/code-step/question.md` (overwrite, one question at
a time) and the ask-user line names that file. It used to append the question to `say.md`. The Stop `say-hook`
empties `say.md` only, so it no longer deletes a question that the main session has not read yet.

`code_step.py`:

- Every verb run (not the hooks, not `status`) empties `question.md` first: a new verb answers or replaces the old
  question.
- `ask_the_user` (review asks) goes through `ask_user` instead of writing its own question block.
- `resume <answer>` at a coder that stopped for the user's answer asks again with the answer in the question:
  "The user answered: <answer>. Send that answer to agent <id> with SendMessage, then run resume." With no stopped
  coder, `resume <text>` is still refused with a rerun of `resume`.

`skills/code/SKILL.md`: `resume <text>` runs `code_step.py resume "<text>"`. The hand-back is `say.md`, then
`question.md`, then the stage queue and the stop lines.

## Evidence

A codefork bench session (tree b3, ticketsim BILL-212 Phase 0, 2026-10-24) stopped when the quality-check cap blocked
the full `npm test`. The main session sent each answer as `/code resume <answer>`. Both times `resume` printed
`ACTION: ask-user` that pointed at an empty `say.md`. The transcript is gone, so the cause is read from the code: the
/code fork runs in the background, the main session's turn ends, and its Stop say-hook empties `say.md` after the fork
wrote the question and before anyone read it. `resume <answer>` was refused, so the answer never reached the run.

The three new tests in `test_code_step_resume.py` fail on the old code (an empty question file after the Stop hook,
a refused `resume <answer>`, a question that a later verb leaves behind) and pass on the new code.

## Result

`bash tests/run.sh`: 2115 tests, 2 failed. Both are `RealPlansTest` cases on the agent-ledger LED-46 plan's level-5
heading, which fail on master too. `test_code_step*.py` (485 tests) and `test_fixes.py` pass, and `ruff check` passes.

## Watch

None. No intake counts empty ask-user hand-backs.

## Back-out

Revert the commit.
