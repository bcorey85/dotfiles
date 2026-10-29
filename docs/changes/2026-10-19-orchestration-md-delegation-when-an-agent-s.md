---
type: "Change"
change_type: "changed"
title: "The main session reads an agent's report before stopping an agent that still shows background work"
description: "When an agent's completion notice says it still runs background work, the main session reads the report, and stops the agent with TaskStop only when the job is done and no work is awaited."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["rule/orchestration"]
evidence: ["judgment"]
watches: []
---

## Change

`orchestration.md` Delegation now has the main session read an agent's report when its completion notice says the agent still runs background work. It stops the agent with TaskStop only when the report says the job is done and names no work it waits on, and it leaves an agent that waits on its own work

## Evidence

judgment

## Result

A worker's command timed out. The worker handed back its report, but its completion notice said that it still ran background work, and it stayed in the agent panel. The user read it as live work and asked how to clear it. TaskStop on that agent cleared it.

## Watch

none, the effect is in the agent panel only.

## Back-out

delete the bullet
