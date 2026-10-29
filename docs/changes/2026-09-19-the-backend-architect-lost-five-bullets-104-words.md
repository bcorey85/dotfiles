---
type: "Change"
change_type: "changed"
title: "The backend architect lost five bullets (104 words, 455 remain in the agent file)"
description: "The backend architect lost five bullets (104 words, 455 remain in the agent file)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-19T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/backend-architect"]
evidence: ["removal round"]
watches: []
---

## Change

The backend architect lost five bullets (104 words, 455 remain in the agent file). From the list of what a complete plan specifies: API endpoints, async tasks, and quality mechanics. From the edge-case list: route order and validator precision, with the intro example that named route order. The deviations bullet, the no-op bullet, the return-type bullet, and the scope fence stay. The opencode copy keeps every bullet, because it runs a different model.

## Evidence

removal round

### Anchor reasons

Anchor `agents/backend-architect.md`, section `## Scope Fence: Backend Only` (evidence: removal round):

Design the backend only, read anything, and hand the API contract to the frontend architect. On a ticket with a web client, every Opus plan with the fence stayed out of the client files, named the frontend architect, and gave it the API contract. Every plan without the fence put the client files into its steps and named no frontend architect. The plans without it also cost about a third more Opus tokens. The text that left with the fence also held the role line and the research block of the core, so the round cannot split the three. An earlier round kept the fence in both texts on a ticket with no frontend.

Anchor `agents/backend-architect.md`, section `## What a Complete Plan Specifies` (evidence: unproven, removal round):

One bullet: deviations from existing patterns, each with the reason. Unproven: on a ticket with routes, a database, and a scheduled job, no Opus plan used the word, with the bullet or without it, and no plan had a clear deviation to report. The bullet fired in one plan of an earlier round. Gone: the bullets for API endpoints, async tasks, and quality mechanics. With the whole list removed, every Opus plan still gave validation rules, status codes, and auth rules for each endpoint, at least three of the four async aspects of the job, the transaction boundaries, and a batched label load. The data-models bullet left earlier on the same kind of evidence. No run held the list with only this bullet.

Anchor `agents/backend-architect.md`, section `## Edge Cases to Explicitly Address` (evidence: removal round, unproven):

No-op behavior and the return type of a conditional operation, each checked against the stack first. The no-op bullet stays on one count: most Opus plans with it say that a no-op emits no event, and most plans without it do not say so. Every plan handled the no-op itself with or without the bullet, and every plan put the guard before the write. So the count shows that the text is followed, not that it changes the build. The return-type bullet is unproven: every plan answered a no-op with a 409, so no plan had a conditional return to type. Gone: the route-order bullet, the validator bullet, and the intro example that named route order. With the whole list removed, every Opus plan still put the static route before the parameter route, and still fixed the validator that drops a valid 0. No run held the list with only these two bullets.

Anchor `agents/frontend-architect.md`, section `## Scope Fence: Frontend Only` (evidence: unproven):

What it designs, that it may read anything including backend code, and the handoff to the backend architect with the API requirements it must specify. The handoff clause is the seam the coder-side split result questions, and nothing has measured it here.

## Result

On a ticket with routes, a database, a scheduled job, and a web client, the Opus architect held every checked behavior of the five bullets in every plan with both lists gone: validation rules, status codes, auth rules, at least three of the four async aspects of the job, transaction boundaries, a batched load, the static route before the parameter route, and the fix for a validator that drops a valid 0. The plans without the lists cost about a fifth fewer output tokens and came back about a quarter faster, with few runs behind both numbers. The scope fence works: every plan with it stayed out of the client and handed the frontend architect a contract, and every plan without it designed the client files, at about a third more Opus tokens. The no-op bullet stays because its events clause is followed: most plans with it say that a no-op emits no event, and most plans without it do not. The deviations bullet, the return-type bullet, and the research flag of the architect core showed no effect with or without their text, and they stay unproven. The gain is 104 always-loaded words on an Opus agent, with no loss on any checked behavior. No run held the lists with only the bullets that remain, and the frontend architect never ran.

## Watch

—

## Back-out

—
