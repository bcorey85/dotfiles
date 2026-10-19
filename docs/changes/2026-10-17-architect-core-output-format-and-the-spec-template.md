---
type: "Change"
title: "`architect-core` Output Format and the spec template: the `Reuse:` line on every implementation step is"
description: "`architect-core` Output Format and the spec template: the `Reuse:` line on every implementation step is removed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-17T00:00:00-05:00"}
seq: 6
components: ["skill/architect-core"]
evidence: ["seeded round"]
watches: []
---

## Change

`architect-core` Output Format and the spec template: the `Reuse:` line on every implementation step is removed. Both files match their text from before that edit. The edit watch for it is removed

## Evidence

seeded round

### Anchor reasons

Anchor `agents/plan-verifier.md`, section `## Output Format` (evidence: removal round):

The report block. Byte-identical in both arms.

## Result

Removed. Plans without the line already named the money-sum helper in the step, 3 of 3. One Sonnet coder built each of 6 plans, and no coder wrote its own sum, 0 of 3 with the line and 0 of 3 without. Every coder typed the client-not-found code inline once in both arms. The line cost 20% more Opus architect output (336,000 against 280,000 tokens over 3 plans) and 15% more plan words

## Watch

—

## Back-out

—
