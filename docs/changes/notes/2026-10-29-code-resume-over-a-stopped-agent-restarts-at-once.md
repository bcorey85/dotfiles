---
type: "Change"
change_type: "fixed"
title: "/code resume over an agent stopped with TaskStop restarts at once instead of waiting out the cap"
description: "When the coder or review-loop that resume waits on, or the fork that launched it, was stopped with TaskStop and has not handed back since its newest launch or resume, resume on an open run prints a `start --restart --coder-stopped` rerun at once; a planless run asks for the task text first. A finished run and a run ready for `verify` go on as before."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T23:59:00-05:00"}
seq: 388
kind: "fix"
components: ["script/code-step"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_resume_over_a_stopped_coder_reruns_a_restart_with_coder_stopped_at_once"
asked: ""
proof: []
unmeasured: "Whether a live TaskStop reaches the log hook before the settings.json matcher names TaskStop."
---

## Change

- `code_step.command_resume`: reads the `task-stop` record through `stopped_awaited_agent_id`. With the awaited agent
  stopped, a plan run refuses with one rerun, `start --restart --coder-stopped` plus its phase, modifier and
  --headless flags; a planless run asks the user for the task text. A stale phase still goes to its own question,
  and a finished run or a run ready for `verify` is not redirected.
- `code_step_core.plan_restart_command`: the plan run's restart command, now shared by `restart_instruction`.

## Evidence

- After a session stopped a /code fork and its coder with TaskStop, `resume` on the same run waited the full 1800 s
  cap for a hand-back that never came.

## Result

- Three new tests fail before the change (a stopped coder, a stopped review-loop, a planless run) and pass after;
  a fourth pins that a coder resumed with SendMessage after its stop is waited on and read as before. Two more,
  a finished run and a run ready for `verify` with a stopped launch, fail against the first draft of the change,
  which redirected both, and pass after.

## Watch

—

## Back-out

Revert the commit.
