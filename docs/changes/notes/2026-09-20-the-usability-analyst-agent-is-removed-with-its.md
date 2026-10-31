---
type: "Change"
change_type: "removed"
title: "The usability analyst agent is removed, with its opencode copy"
description: "The usability analyst agent is removed, with its opencode copy."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 18
kind: "behavior"
components: ["agent/usability-analyst"]
evidence: ["census"]
watches: []
---

## Change

The usability analyst agent is removed, with its opencode copy. The user decided the removal.

## Evidence

census

## Result

No dispatch of the agent shows in ten weeks of the dispatch log, live or bench. No skill, command, script, hook, or other agent named it, so no consumer needed a change. Its description put one line into the agent menu, and a main session reads that menu again on every request. In the two weeks measured, that line cost about 0.33M cache-read tokens a week in live sessions. Effect unmeasured. The expected gain is the end of that cost in sessions that start after the removal. No live check is owed, because nothing dispatched the agent.

## Watch

—

## Back-out

—
