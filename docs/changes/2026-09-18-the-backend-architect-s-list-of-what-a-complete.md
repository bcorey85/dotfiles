---
type: "Change"
change_type: "changed"
title: "The backend architect's list of what a complete plan specifies lost its data-models bullet (14 words"
description: "The backend architect's list of what a complete plan specifies lost its data-models bullet (14 words, 559 remain in the agent file)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 12
kind: "behavior"
components: ["agent/backend-architect"]
evidence: ["removal round"]
watches: []
---

## Change

The backend architect's list of what a complete plan specifies lost its data-models bullet (14 words, 559 remain in the agent file). The Data Models placeholder of the plan template names the same fields. The other four bullets, the edge-case list, and the Reuse Map how-to stay.

## Evidence

removal round

### Anchor reasons

Anchor `agents/backend-architect.md`, section `## Plan Body Sections (backend)` (evidence: removal round, census):

The five body headings and their placeholders. The Reuse Map how-to stays: search first, say so when the map is empty, and give one reason line for each new unit. Every Opus plan with the how-to held the reason line, and no plan without it did. The plans without it still listed the reused units with file paths. This shows that the text is followed, not that it stops a duplicate. The sentence that seeds the map from the research document is contract: the research agent produces that section.

Anchor `agents/frontend-architect.md`, section `## What a Complete Plan Specifies` (evidence: unproven):

Six required contents: component hierarchy with typed interfaces, state and data flow, API integration with loading/error/empty states, styling, accessibility, and deviations with reasons. Never varied.

## Result

With the whole list gone, every plan still gave typed data models with constraints and a migration note. The Reuse Map how-to stays because it works: every plan with it gave a reason line for each new unit, and no plan without it did. The other bullets and the edge-case list stay unproven, because a CLI ticket with no HTTP surface, no database, and no async work cannot fire them. With all of this prose gone, the architect held the plan envelope, the ledger decisions, and the truth about the planted code in every run, and its plans came out slightly longer, not shorter. The architect also needs no rule that tells it to check a decision ledger against the code: on two planted mismatches it read the code and stated the truth in every plan.

## Watch

—

## Back-out

—
