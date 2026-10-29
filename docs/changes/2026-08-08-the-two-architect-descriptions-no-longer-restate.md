---
type: "Change"
change_type: "changed"
title: "The two architect descriptions no longer restate the test for skipping design work"
description: "The two architect descriptions no longer restate the test for skipping design work, and name where the whole test lives."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 22
kind: "behavior"
components: ["agent/backend-architect", "agent/frontend-architect"]
evidence: ["census"]
watches: []
---

## Change

The two architect descriptions no longer restate the test for skipping design work, and name where the whole test lives

## Evidence

census

### Anchor reasons

Anchor `agents/frontend-architect.md`, section `## CRITICAL: Pattern Consistency — Reuse Before Creating` (evidence: unproven):

Five numbered rules: search for precedents, reuse before designing new, modify in one place so all usages hold, same function means same component, and follow existing styles. Fresh-eyes duplication detection is the single best-measured effect in the system, but it was measured in a reviewer after the fact, never in an architect before the fact. Whether a prompt can prevent the duplication that a reviewer reliably catches is open.

## Result

The skill's test is a four-part conjunction; the descriptions had it as one part, so they authorized skipping design on changes the skill would have sent to an architect. They stay prose rather than a pointer because they are read when choosing an agent, without the skill loaded

## Watch

—

## Back-out

—
