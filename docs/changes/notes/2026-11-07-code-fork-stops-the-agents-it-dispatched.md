---
type: "Change"
change_type: "fixed"
title: "/code fork stops the agents it dispatched"
description: "The caller cancels a /code fork with a stop message, and the fork stops every agent it dispatched and names each one before it ends."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:28:20-06:00"}
seq: 4
kind: "fix"
components: ["skill/code", "agent/code-fork"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_code_fork_is_cancelled_with_a_stop_message_and_stops_every_agent_it_dispatched"
asked: ""
proof: []
unmeasured: ""
---

## Change

The /code description tells the caller to SendMessage the fork `stop` and TaskStop it only after its stop names every dispatched agent as stopped. code-fork TaskStops its running agents on a stop the user or outside session sent. No opencode port of code-fork exists.

## Evidence

judgment: a TaskStop of a /code fork left its coder running; it re-created deleted files and edited dozens of tracked files. The new guidance test fails on the base commit and passes after.

## Result

Guidance test passes; rule anchors check clean.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.

