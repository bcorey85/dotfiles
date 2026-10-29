---
type: "Change"
title: "A reviewer killed with no tool-use id no longer blocks the hand-back"
description: "The loop transcript reader closes a background agent launch on a task notification that names the agent by its task id, so a reviewer the rate limit killed stops counting as pending and the review loop can hand back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T21:10:20-05:00"}
seq: 219
kind: "fix"
components: ["script/review-loop-gate", "script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::StopRowTest::test_a_reviewer_the_rate_limit_killed_is_closed_by_its_task_id_notification"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_gate.py` `LoopTranscript`: it records the task id of every task notification. A background agent
  launch whose agent id has a notification no longer counts as open, and a resume closes on a later notification
  under the agent's id. The hand-back hook's open-work check, the stop hook and the open-child gate all read this
  count.

## Evidence

- A review loop resumed after a rate-limit reset had one reviewer that the rate limit killed. The hand-back hook
  kept counting it as pending and refused every hand-back, so the loop hit its cap with six fixes and never handed
  back. The commit gate stayed dirty.
- The reader closed a launch only on a notification carrying `<tool-use-id>` or on an agent message. A dead agent
  sends no agent message, and an agent's notification can carry only `<task-id>`, its agent id.

## Result

- The new test fails before (the killed reviewer stays open) and passes after.

## Watch

—

## Back-out

Revert the commit.
