---
type: "Change"
change_type: "fixed"
title: "/code continue resumes the saved plan"
description: "`/code continue` (or `/code` with no text) now runs `code-step.py start` with no argument, which resumes the saved plan. Before, the skill passed the word to `start` as task text, and code-step began a planless run that dropped the plan, left the phase unticked and cut files from the commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T16:19:29-05:00"}
seq: 6
kind: "fix"
components: ["skill/code"]
evidence: ["work incident", "repro"]
watches: []
---

## Change

- The /code skill runs `code-step.py start` with no argument when the task text is empty or is `continue`. Any other text still goes to `start` as before.

## Evidence

Work incident: an agent-ledger /code run printed "Planless task reviewed" on a planned task and offered a commit that staged 1 of 14 changed files. Its spec still showed Phases 1 and 2 unticked after their code was committed. Cause: the skill passed `continue` to `start` as task text. `start_planless` wrote a state with no plan and a fresh file baseline, so `finish_phase` took the planless branch and `phase_commit` left out every file that was dirty at that start. Repro: a scratch repo with a 2-phase plan gives the same output after two `start continue` calls.

## Result

Live on save. The script-side guard (refuse a planless start over a plan with an unfinished phase, unless `--task` or `--restart`) goes into the next code-step bundle.

## Watch

None. A fix: the repro proves it.

## Back-out

Delete the `continue` sentence from step 1 of `skills/code/SKILL.md`.
