---
type: "Change"
change_type: "removed"
title: "Weak assertions are now checked once at the branch recap, not after every phase"
description: "The weak-assertion check runs at the recap boundary, because a single phase cannot see assertions that are absent."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 10
kind: "behavior"
components: ["skill/test-audit", "agent/test-intent-reviewer"]
evidence: ["remedy round"]
watches: []
---

## Change

The weak-assertion check now runs at the recap boundary. Before, it ran after every phase.

## Evidence

remedy round

## Result

Phase scope structurally can't see _absent_ assertions

## Watch

—

## Back-out

—
