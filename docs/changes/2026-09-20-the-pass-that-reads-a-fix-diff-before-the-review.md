---
type: "Change"
title: "The pass that reads a fix diff before the review loop exits is now bounded by the diffs it has not read"
description: "The pass that reads a fix diff before the review loop exits is now bounded by the diffs it has not read rather than by a fixed count, so a repair ordered by a specialist reviewer is read as well and no loop ends on an unreviewed code change."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 12
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The pass that reads a fix diff before the review loop exits is now bounded by the diffs it has not read rather than by a fixed count, so a repair ordered by a specialist reviewer is read as well and no loop ends on an unreviewed code change.

## Evidence

census

### Anchor reasons

Anchor `agents/goal-blind-researcher.md`, section `## Steps` (evidence: unproven):

The four-step chain: questions, leak check, a repair loop bounded at two cycles, then research with the questions path and nothing else. The bound is what stops an unresolvable leak from looping, and the nothing-else clause is what keeps the goal away from the research agent. Neither has been exercised.

## Result

Effect unmeasured. Live checks: the share of loops with a fix coder whose last dispatch is a reviewer, the count of passes per loop, and the share of specialist-driven repairs that a pass reads.

## Watch

—

## Back-out

—
