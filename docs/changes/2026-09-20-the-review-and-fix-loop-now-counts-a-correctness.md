---
type: "Change"
title: "The review-and-fix loop now counts a correctness round when it dispatches a reviewer"
description: "The review-and-fix loop now counts a correctness round when it dispatches a reviewer, not when it dispatches a fix, and the count starts at zero, so the number it reports is the number of rounds it ran."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 11
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review-and-fix loop now counts a correctness round when it dispatches a reviewer, not when it dispatches a fix, and the count starts at zero, so the number it reports is the number of rounds it ran. The written round budget is set to two against that honest count, which is what the loop already did in practice. The handoff schema and the review audit read the new count.

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/handoff-block.md`, section `## Canonical schema` (evidence: census):

The handoff schema itself. `/code` and `/fix` produce it, the loop agent takes it as review scope, and the reviewer verifies the prior issues it carries; the two iteration budgets ride in it between caller and loop. The correctness count starts at zero and counts rounds run. By judgment, the tests-run example is now a scoped test command, so the example does not invite a full run. Effect unmeasured.

## Result

Effect unmeasured. Live checks: the share of packets whose reported round count matches the reviewer dispatches in the run, the spread of that count, and the share of runs stopped by the budget.

## Watch

—

## Back-out

—
