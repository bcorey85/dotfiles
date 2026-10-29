---
type: "Change"
change_type: "changed"
title: "The 12 agents that named the `sonnet` alias, the coder among them, now name `claude-sonnet-5-5` in full"
description: "The 12 agents that named the `sonnet` alias, the coder among them, now name `claude-sonnet-5-5` in full."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 9
kind: "behavior"
components: ["agent/coder"]
evidence: ["census"]
watches: []
---

## Change

The 12 agents that named the `sonnet` alias, the coder among them, now name `claude-sonnet-5-5` in full. This corrects the earlier rows that said the alias moved these agents and the coder to Sonnet 5.5: at work the alias resolved to Sonnet 5

## Evidence

census

## Result

In the two work days after the switch, the work coder made 29 dispatches on Sonnet 5 and none on Sonnet 5.5, so it did not run the model that the coder round passed. Dispatches that pass `sonnet` at the call site, and the general-purpose agent, still resolve through the alias

## Watch

—

## Back-out

—
