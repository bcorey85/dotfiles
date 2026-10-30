---
type: "Change"
change_type: "fixed"
title: "code_step start takes text after a plan file as run notes for the next phase"
description: "`/code <plan file> — <brief>` starts the plan's next phase with the brief as run notes instead of refusing the text and stopping for the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T17:31:47-05:00"}
seq: 282
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_brief_after_a_plan_with_no_phase_starts_the_next_phase_with_it_as_run_notes"
asked: ""
proof: []
unmeasured: "Run-note refusals are not logged; no intake number reads them."
---

## Change

`start <plan file inside the repo that has phases> <text>` with no phase now takes the text as run notes and starts the plan's next open phase, as
`start <plan> --phase <id> <text>` already did for a named phase. The text reaches the coder brief, or a closing phase's
skill, under "Run notes from the user", word for word (a leading dash stays). A ticket id followed by text with no phase
still stops with both choices, since the id may be the first word of a task. Two plan files before the text, with or
without a phase, now stop with that same refusal instead of dropping the second plan. A plan outside the repo with a
phase keeps its notes in the question that asks for a plan inside the repo. `start --help` says the same.

## Evidence

judgment: a worker ran `/code <plan path> — <short brief>`, the script refused the text after the plan as "not task
text", and the worker stopped to ask the human. The new test fails on the base commit with that refusal in both forms
(brief as separate words, brief as one argument) and passes after.

## Result

A brief after an in-repo plan path that has phases reaches the coder without a stop for the user.

## Watch

None.

## Back-out

Revert the commit; `start <plan file> <text>` then refuses again and prints the plan start and the `--task` start.
