---
type: "Change"
change_type: "fixed"
title: "Code fork hands questions back instead of messaging"
description: "A /code fork's question reaches the session that ran /code through question.md in the hand-back and is never sent by message, even when the task names a session to ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T03:58:57-05:00"}
seq: 165
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeForkToolsTest::test_the_code_fork_hands_a_question_back_even_when_the_task_names_a_session_to_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

- /code skill: a new rule says a question reaches the session that ran /code through question.md in
  the fork's hand-back and is never sent by message, even when the task text names a session or orchestrator to ask.
  The session that ran /code relays it.

## Evidence

- A /code fork whose brief named an orchestrator to ask reported no SendMessage tool in its session, so the question
  never reached that orchestrator. The fork's agent does not disallow SendMessage, and the skill's `allowed-tools` does
  not list it; why the tool was missing is not confirmed, so the fix routes questions through the hand-back, which
  needs no extra tool.

## Result

- A fork's question always reaches the session that started it, which has the tools to pass it on.

## Watch

—

## Back-out

Revert the commit.
