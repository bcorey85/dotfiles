---
type: "Change"
change_type: "changed"
title: "`/eng-spec` goal-blind research order"
description: "`/eng-spec` goal-blind research order."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["skill/eng-spec"]
evidence: ["clean result"]
watches: []
---

## Change

`/eng-spec` goal-blind research order

## Evidence

clean result

### Anchor reasons

Anchor `agents/goal-blind-researcher.md`, section `## The one rule everything else serves` (evidence: unproven):

Never read the ticket; the path is for forwarding only, and opening, quoting, or inferring a slug from it are violations. Also never edit the questions file — repair is a re-dispatch. This is the invariant the whole goal-blind phase rests on, and no round has tried to break it.

Anchor `agents/goal-blind-researcher.md`, section `## Return` (evidence: unproven):

The paths-and-process-facts block, one line per repaired question, and the ban on summarizing the research document. Never varied.

Anchor `agents/spec-research.md`, section `## The one rule` (evidence: unproven):

No knowledge of any broader goal and no acquiring one: read only the questions file, never the ticket beside it, and ignore any extra context the dispatch carries. The receiving half of the goal-blind invariant. Untested.

Anchor `agents/spec-questions.md`, section `## What NOT To Do` (evidence: unproven):

Run no research, leak no intent outside the snapshot, twelve questions maximum. Never varied.

## Result

The one step in the system with unambiguous evidence behind it

## Watch

—

## Back-out

—
