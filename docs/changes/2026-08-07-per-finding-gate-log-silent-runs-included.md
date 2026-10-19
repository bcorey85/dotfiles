---
type: "Change"
title: "Per-finding gate log (silent runs included)"
description: "Per-finding gate log (silent runs included)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-07T00:00:00-05:00"}
seq: 1
components: ["script/log-review-finding", "skill/review"]
evidence: ["metric audit"]
watches: []
---

## Change

Per-finding gate log (silent runs included)

## Evidence

metric audit

### Anchor reasons

Anchor `skills/_shared/finding-log.md`, section `# Per-Finding Gate Log` (evidence: census):

Names the file as the one instruction for every finding-emitting gate. Four skills and the loop agent's per-finding step cite it by path.

## Result

Aggregate rows carry no `file:line` and no denominator — per-gate yield and marginal contribution were not computable

## Watch

—

## Back-out

—
