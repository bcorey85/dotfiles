---
type: "Change"
change_type: "removed"
title: "`/eng-spec` no longer switches a plan to deep tier because one phase is high-risk"
description: "`/eng-spec` stays at its normal tier on a high-risk phase instead of pricing the whole plan at deep tier."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["skill/eng-spec"]
evidence: ["cost profile"]
watches: []
---

## Change

`/eng-spec` no longer switches a plan to deep tier because one phase is high-risk. Before, a high-risk phase made the whole plan run at deep tier.

## Evidence

cost profile

## Result

Priced a whole plan at deep tier to buy one phase

## Watch

—

## Back-out

—
