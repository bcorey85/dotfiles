---
type: "Change"
change_type: "fixed"
title: "/code start over a run whose coder was stopped reruns a restart instead of waiting out the cap"
description: "The log hook records each TaskStop; when the open run's awaited agent, or the fork that launched it, was stopped, start refuses with one `start --restart --coder-stopped` rerun and the stop hook no longer steers the fork to resume."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T23:59:00-05:00"}
seq: 298
kind: "fix"
components: ["script/code-step"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_task_start_over_a_run_whose_coder_was_stopped_reruns_a_restart_with_coder_stopped"
asked: ""
proof: []
unmeasured: "Whether a live TaskStop of a named /code fork reaches the log hook with the fork's agent id in tool_response.task_id."
---

## Change

- `code_step_hooks.py`: the log hook logs a `task-stop` event for each TaskStop call, with the stopped task's id taken
  from the result (a fork stopped by its name, such as `code`, reports its agent id there). Each `launch` event now
  records `launched_by`, the launching fork's agent id.
- `code_step_core.stopped_awaited_agent_id`: the agent the next verb waits for, when a `task-stop` names it or the
  fork that launched it after its newest launch or SendMessage resume.
- `code_step_start.open_run_refusal`: with that agent stopped, `start` (bare or with new work) refuses with one rerun,
  `start --restart --coder-stopped ...`, in place of the resume/restart/abort choice.
- `code_step_hooks.open_fork_block`: no fork block, the stop hook included, while the awaited agent is stopped.
- `settings.json`: the log hook's matcher needs `TaskStop` added. The settings gate refused that edit, so it is not in
  this change.

## Evidence

- A session stopped a /code fork and its coder with TaskStop, then ran /code with a new task. `start` was refused
  over the open run, the stop hook sent the fork to `resume`, and `resume` waited the full 1800 s cap.
- Transcripts: a TaskStop of a /code fork by the name `code` returns `task_id` set to the fork's agent id and
  `task_type: local_agent`; stopping an agent also kills the agents it launched (status `killed`).

## Result

- Two new tests fail before the change (resume choices) and pass after; a third pins that a SendMessage resume after
  the stop brings back the resume choice and the stop-hook block.

## Watch

—

## Back-out

Revert the commit.
