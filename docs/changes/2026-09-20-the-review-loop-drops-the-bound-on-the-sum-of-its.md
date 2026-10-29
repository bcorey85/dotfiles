---
type: "Change"
change_type: "changed"
title: "The review loop no longer checks the sum of its two round counters, a bound that could never trigger"
description: "The review loop no longer bounds the sum of its two round counters, a check that could never trigger."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 13
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review loop no longer bounds the sum of its two round counters. Each channel refuses its own third round, so the sum can never reach the value that bound tested. The branch it guarded was unreachable in every saved run.

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/handoff-block.md`, section `## Consumer rules` (evidence: census, judgment):

What each consumer must do with the block: the reviewer reads the prior issues and the scope from it, and the two iteration counters are split between caller and loop here. Every rule the census traced to a consumer stands, including the ban on folding the two counters. Cut by judgment since: the reason the split exists, and the versioned-interface framing above the add-a-field rule.

## Result

Effect unmeasured. Live check at the next intake: the share of runs that return the cap-reached status, which must not move, because the two channel caps produce it.

## Watch

—

## Back-out

—
