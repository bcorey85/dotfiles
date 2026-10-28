---
type: "Change"
title: "code-step: a restart refuses while the capped coder has not handed back"
description: "After the coder wait cap, `start --restart` dispatched a new coder while the silent one could still be editing the same tree; it now refuses and names the coder to stop, and `--coder-stopped` passes once it is stopped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T14:24:16-05:00"}
seq: 196
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_restart_over_the_coder_cap_refuses_until_that_coder_is_stopped"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `start` over a stopped run refuses when the run's coder (the resumable coder, or the newest launch at a coder-cap
  stop) has a launch or SendMessage resume newer than its newest hand-back. The refusal names the coder to stop with
  TaskStop and prints the same start with `--coder-stopped`.
- Every stop that names a restart over a stopped run (the coder-cap stop, the plan-edit coder cap, the stopped-coder
  question, the unrecorded-state stop) tells the session to stop that coder first when it is still out, and its
  restart command carries `--coder-stopped`.
- A coder that handed back, or a launch with no agent id, does not block.

## Evidence

- A resumed coder ran beside a live copy of itself on one tree. The coder-cap stop was the one script path that offered
  a new coder while the silent one still ran.

## Result

- No restart puts a second coder on a tree while the first may still edit it.

## Watch

—

## Back-out

Revert the commit.
