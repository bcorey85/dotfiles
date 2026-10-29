---
type: "Change"
change_type: "removed"
title: "`code-reviewer` stays: removing it could not be shipped"
description: "Removing the `code-reviewer` agent was judged not shippable, because the comparison without it could not be produced."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 6
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["VOID round"]
watches: []
---

## Change

The `code-reviewer` agent stays in place. Removing it was judged not shippable, because the comparison without it could not be produced.

## Evidence

VOID round

## Result

**Not shippable** — the OFF cell can't be produced

## Watch

—

## Back-out

—
