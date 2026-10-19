---
type: "Change"
title: "`/code` and `/review`: end the turn only at a STOP (or a wait, in `/review`)"
description: "`/code` and `/review`: end the turn only at a STOP (or a wait, in `/review`)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 1
components: ["skill/code", "skill/review"]
evidence: ["census"]
watches: []
---

## Change

`/code` and `/review`: end the turn only at a STOP (or a wait, in `/review`). Take any other reversible step without asking leave, and report it afterward. Ask only before an irreversible step, one that leaves the machine, or a choice between two defensible paths

## Evidence

census

## Result

At work, 1957 of 3140 turn ends with a human reply asked no question: they were a report or a phase end. Effect unmeasured.

## Watch

the no-question row of the turn-end census.

## Back-out

delete the one paragraph in each skill
