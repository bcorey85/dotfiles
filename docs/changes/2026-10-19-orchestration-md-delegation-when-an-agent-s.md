---
type: "Change"
title: "`orchestration.md` Delegation: when an agent's completion notice says it still runs background work"
description: "`orchestration.md` Delegation: when an agent's completion notice says it still runs background work, the main session reads the report."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 5
components: ["rule/orchestration"]
evidence: ["judgment"]
watches: []
---

## Change

`orchestration.md` Delegation: when an agent's completion notice says it still runs background work, the main session reads the report. It stops the agent with TaskStop only when the report says the job is done and names no work it waits on, and it leaves an agent that waits on its own work

## Evidence

judgment

## Result

A worker's command timed out. The worker handed back its report, but its completion notice said that it still ran background work, and it stayed in the agent panel. The user read it as live work and asked how to clear it. TaskStop on that agent cleared it.

## Watch

none, the effect is in the agent panel only.

## Back-out

delete the bullet
