---
type: "Change"
title: "A /code fork replies at once to a mid-run scope message"
description: "The /code skill says a run takes no scope change mid-run: the fork replies to the sender with SendMessage at once and never passes the message on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:55:00-05:00"}
seq: 137
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeForkToolsTest::test_the_code_fork_can_reply_at_once_to_a_mid_run_scope_message"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `/code` step 5: a run takes no scope change mid-run. A message that reaches the fork during the run gets an
  immediate SendMessage reply to its sender that it was not applied and how to carry it. The fork then goes on.
- The reply route, not a forward: carrying the message to the next coder or review round needs new run state.
- A test pins the rule text and that `code-fork` does not disallow SendMessage.

## Evidence

- A main session sent a scope addition to a running /code fork after its coder had returned. The fork dropped it,
  and the sender learned that only from the fork's final report.

## Result

- A sender of a mid-run scope message hears at once that it was not applied.

## Watch

—

## Back-out

Revert the commit.
