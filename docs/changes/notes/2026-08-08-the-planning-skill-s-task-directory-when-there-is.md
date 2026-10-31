---
type: "Change"
change_type: "changed"
title: "The planning skill names a keyless task directory for the codebase area, not the change"
description: "The planning skill's task directory, when there is no ticket key, is now named for the area of the codebase being changed rather than for the change."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 20
kind: "behavior"
components: ["skill/eng-spec"]
evidence: ["census"]
watches: []
---

## Change

The planning skill's task directory, when there is no ticket key, is now named for the area of the codebase being changed rather than for the change

## Evidence

census

### Anchor reasons

Anchor `agents/spec-questions.md`, section `## Inputs (from your dispatch)` (evidence: unproven):

The source path, the task directory, and the optional flagged-rewrites input that turns a re-dispatch into an edit of the existing file rather than a regeneration. Never varied.

Anchor `agents/spec-questions.md`, section `## Question Rules` (evidence: unproven):

Document-what-exists framing, one area per question, never mention what is being built, and the test that a skilled reader knows the areas and nothing of the goal. The producing half of the goal-blind invariant, and the text the leak check audits. Untested.

Anchor `agents/spec-questions.md`, section `## File Format` (evidence: unproven):

The numbered question template and the exploration map with a neutrally stated reason per area. Never varied.

## Result

That path is handed to the agents that research the codebase without being allowed to know the goal, so a descriptive folder name told them the problem, the intended fix, and that current behavior was wrong. It is the one property of the design that nothing downstream can restore once lost. A ticket key always stays in the name: it is opaque to anyone who has not opened the ticket, and it is what makes the directory findable from a branch or the tracker. Keyless names carry the date, since an area name on its own repeats every time that area is touched

## Watch

—

## Back-out

—
