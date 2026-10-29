---
type: "Change"
title: "resume with task text over an open run stops instead of resuming"
description: "`code_step.py resume <text>` over an open run with no coder waiting for an answer now stops on the user's word with resume, restart and abort, instead of rerunning a bare `resume` that went on with the old task and dropped the new one."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T13:21:46-05:00"}
seq: 267
kind: "fix"
components: ["skill/code", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_resume_with_task_text_over_an_open_run_stops_on_the_users_word_and_runs_neither_task"
asked: ""
proof: []
unmeasured: ""
---

## Change

`resume <text>` with no stopped coder waiting for an answer used to refuse with `ACTION: rerun` and a bare `resume`.
The /code skill runs a rerun command at once, so the open run went on and the new task was dropped; the only trace
was the note "For new work, use `start --task`". Over an open run the refusal now names the run and its stage, says
the text was not run, and stops with three choices on the user's word: `resume` (go on with the open run),
`start --restart --task '<text>'` (drop it and start the text) and `abort` (close it). The restart line is built as
`start`'s own refusal builds it, so a `+fast` or `+deep` modifier stays out of the task text. Over another session's
run both refusals stop (never `ACTION: rerun`, which the skill runs at once and which would drop the text) with only
`status` listed (the `start` refusal also lists `verify` when the phase awaits it), the text or task named as not run,
and the note that the run needs the user's word (`OTHER_SESSION_RUN_NOTE`, in `code_step_start.py`).
`resume <text>` with no run open goes to `start` as before.

`start` with new work over an open run already stopped on the user's word. Its refusal now also says the task was not
started and offers `abort`. Both refusals share `open_run_reason` and their notes in `code_step_start.py`.

## Evidence

A probe of each way new task text reaches an open run: `start <text>`, `start --task-file`, `start` over a stopped
run, and `resume <text>`. Only `resume <text>` printed one command to rerun, the bare `resume` of the old task.

## Result

The new tests fail before the change (`ACTION: rerun` with the bare `resume`; no `abort` in the start refusal) and
pass after it.

## Watch

None; the work logs carry no row for a refusal's choices.

## Back-out

Revert `resume_text_refusal`, `open_run_reason`, `restart_command_for`, `is_run_of_another_session` and the notes in
`code_step_start.py` (`OTHER_SESSION_RUN_NOTE` included), its `Refusal` import, the "The task was not started."
line in `open_run_refusal`, the other-session `Refusal(..., stop=True)` return and the added `abort` choice in
`open_run_refusal`, and the `Refusal(*refusal)` unpack in `command_start`, the `Refusal` class, its `typing` import and the `refuse()` stop
change in `code_step_core.py`, the import and call in `command_resume` in `code_step.py`, and the test edits in
`test_code_step_resume.py` and `test_code_step_start_input.py`.
