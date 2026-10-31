---
type: "Change"
change_type: "fixed"
title: "/code acts on a stop question the user already answered"
description: "The code-fork agent runs the verb the user's answer names in place of `resume`, so a routine go-on message no longer re-asks a stop question the user already answered."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T21:00:00-05:00"}
seq: 281
kind: "fix"
components: ["agent/code-fork"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_code_fork_acts_on_a_stop_question_the_user_already_answered"
asked: ""
proof: []
unmeasured: "Whether a worker given the line still re-asks after a go-on message."
---

## Change

- `agents/code-fork.md`: when the user already answered the run's last stop question in this conversation, the fork
  runs the verb that answer names in place of `resume`, or `resume "<answer>"` for a stopped coder, and never asks
  that question again.

## Evidence

- A worker's user answered a stop question in the pane. A routine go-on message from the orchestrator came next,
  the worker took it as the last word, ran `resume`, and asked the same question again. The run idled about 30 minutes.
- `code_step.py` records an answer only when a SendMessage to the stopped coder is logged (`coder_answer_sent`,
  code_step.py:439). An answer given only in the pane leaves no record, so `resume` prints the stop question again.
  So the fix is a line in the agent the fork runs as, not script code.

## Result

- The named test fails before (the line is missing) and passes after.

## Watch

—

## Back-out

Revert the commit.
