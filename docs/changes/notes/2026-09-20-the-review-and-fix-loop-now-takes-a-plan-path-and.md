---
type: "Change"
change_type: "changed"
title: "The review-and-fix loop now takes a plan path and a phase number as dispatch arguments"
description: "The review-and-fix loop now takes a plan path and a phase number as dispatch arguments."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 9
kind: "behavior"
components: ["agent/review-loop", "agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

The review-and-fix loop now takes a plan path and a phase number as dispatch arguments. It passes both to every reviewer it dispatches, with the instruction to read the plan phase-scoped by the shared rule. The implement skill passes them from the phase it already resolved. It omits the phase for a plan file that holds one phase or none, and it passes neither for a pasted plan. The shared file that defines the phase-scoped read now names the diff reviewer as a consumer. The opencode copy of the loop took the same two changes.

## Evidence

census

### Anchor reasons

Anchor `skills/review/SKILL.md`, section `## Arguments` (evidence: removal round):

The argument placeholder. Byte-identical in both arms.

Anchor `skills/fix/SKILL.md`, section `## Arguments` (evidence: removal round):

The argument placeholder. Byte-identical in both arms.

Anchor `agents/spec-research.md`, section `## Steps` (evidence: unproven):

Eight steps: read the questions, answer by exploration, cite file and line, record dormant scaffolding unasked, inventory reusable units unasked, re-open every citation before writing, write the research file, and return the path without summarizing. The citation re-read step is the interesting one — a separate census found gates routinely assert about files they never opened — but that census did not cover this agent.

## Result

Unmeasured. Of 19 live reviewer dispatches, 8 carried no plan at all. The loop's own prompt already held a plan path in 6 of those 8, so the share that carries one can rise from 11 of 19 to 17 of 19. Findings that cite the plan appear in 6 of the 11 dispatches that got a plan, and in 0 of the 8 that got none. The cost falls on the largest model, which the diff reviewer is pinned to. One plan read is about 4,400 tokens at the median, across a range of 1,100 to 10,800. Six more reads a loop cost about 26,000 at the median. Live checks: the share of reviewer dispatches that carry a plan path, and the share of findings that cite the plan. The failure to watch for is a rise in reviewer cost with no rise in plan-cited findings.

## Watch

—

## Back-out

—
