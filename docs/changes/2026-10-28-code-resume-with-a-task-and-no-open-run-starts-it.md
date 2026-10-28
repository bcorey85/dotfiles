---
type: "Change"
title: "/code resume with a task and no open run starts it"
description: "code_step.py resume given text with no run open hands the text to start, so a task file or task text sent with no verb starts a run instead of a refusal that pointed at a bare resume."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 143
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_resume_with_text_that_names_a_task_file_and_no_open_run_starts_a_run_with_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step.py resume <text>` with no run open (no saved state, or a finished run) runs `start <text>`. Task text
  that names a task file starts a planless run with that text. A bare task-file path outside the repo gets start's
  refusal with the `start --task-file <path>` command.
- With a run open, `resume <text>` is unchanged: a stopped coder takes it as the user's answer, and any other stage
  refuses it.
- The usage text names `resume <text>`.

## Evidence

- A /code fork given task text that began with a ticket id ran `resume "<text>"`. The refusal printed a bare `resume`
  as the command to run. The fork ran it, and it started the saved plan's Phase 1 instead of the task.
- The new tests fail on the old script.

## Result

- A task or task file sent to `resume` with no open run starts that task.

## Watch

—

## Back-out

Revert the commit.
