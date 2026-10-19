---
type: "Change"
title: "The implement skill now builds the handoff block at the head of the review dispatch step"
description: "The implement skill now builds the handoff block at the head of the review dispatch step, not at the tail of the summary step, and the step says never to dispatch without it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 4
components: ["shared/handoff-block"]
evidence: ["census"]
watches: []
---

## Change

The implement skill now builds the handoff block at the head of the review dispatch step, not at the tail of the summary step, and the step says never to dispatch without it. The fields of the block did not change.

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/handoff-block.md`, section `# Handoff Block (single source of truth)` (evidence: census, judgment):

Declares this file the one definition of the block, which is why the loop agent cites it by path instead of restating the schema. The declaration and the producer-consumer naming stand word for word. Cut by judgment since: the sentence describing what the block saves the reviewer, which no consumer acts on.

Anchor `skills/_shared/handoff-block.md`, section `## The `why` channel` (evidence: judgment):

The free-text channel that carries intent from caller to loop. No script parses it; its only reader is the human reading a phase summary, so nothing measures whether the guidance changes what is written. Compressed by judgment: the anchor rule, the line-number rule, and the sparseness rule now read as three bullets, with the surrounding explanation gone.

## Result

Three in four live review dispatches from this skill carried no handoff block, so the review loop had to find its scope again with no reasons from the coder, no test command, and no flagged items. The gain sought is review quality. The runs that carried a block still spent several responses on scope, so no token gain is claimed. Effect unmeasured. The live check is the share of review dispatches from the implement skill whose prompt carries the block. It stood at one in four before the change. **Appended 2026-09-21.** The one-in-four figure came from this machine, and it is a guide only. On the work machine the handoff line already stood in 222 of 233 review dispatches from this skill (95%) before the change arrived, so the gain there is at most 5 points. The edit stays, because it costs nothing.

## Watch

—

## Back-out

—
