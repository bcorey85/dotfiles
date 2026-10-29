---
type: "Change"
change_type: "changed"
title: "test-reviewer now checks every expected value a test pins against the ticket or plan"
description: "test-reviewer: a new step reads every expected value a test pins against the ticket or plan."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/test-reviewer", "skill/fix"]
evidence: ["reviewer replay"]
watches: []
---

## Change

test-reviewer: a new step reads every expected value a test pins against the ticket or plan. An assertion the ticket contradicts is a `fix` (loosen it to what the spec says); a detail the ticket leaves open is an `ask` and the assertion stays; where the acceptance criteria say more than the ticket, the ticket wins. New report section for these findings

## Evidence

reviewer replay

### Anchor reasons

Anchor `agents/test-reviewer.md`, section `## Output Format` (evidence: removal round, reviewer replay):

The scope header, the health grade, the seven finding sections, and the summary. Kept verbatim; every run in both arms produced it, and the section a plant landed in was the same across arms. An eighth finding section holds the assertions that the spec does not support, from the step that checks pinned values against the spec. Same replay as that step.

## Result

Replayed on five finished trees whose tests agreed with the code but failed on a reference implementation (21 such tests). The old reviewer flagged 2, both as questions. The new one flagged 17: 6 as fixes (every case where a test pinned behavior the ticket rules out) and 11 as questions, and it told the coder to weaken no correct test. A draft that marked every unstated detail as a fix caught 12 as fixes but told the coder to weaken 13 correct tests, so it was not shipped. Cost per review: Opus output +22% (6434 vs 5277 tokens), about 12 s more, and about 3 more questions for the user. **Reverted the same day.** Acceptance criteria are written from the ticket and always outrank it, so the ticket-over-criteria rule that produced every fix finding is wrong. With the criteria on top, the step had no measured gain left to pay for its cost

## Watch

—

## Back-out

—
