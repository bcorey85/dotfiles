---
type: "Change"
change_type: "changed"
title: "The coder agent now runs on Opus in place of Sonnet, for every dispatch: builds from a plan"
description: "The coder agent now runs on Opus in place of Sonnet, for every dispatch: builds from a plan, fix coders in the review loop, refactor and dependency work."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["model round"]
watches: []
---

## Change

The coder agent now runs on Opus in place of Sonnet, for every dispatch: builds from a plan, fix coders in the review loop, refactor and dependency work. The prompt text does not change.

## Evidence

model round

## Result

On two bench rounds with the full architect plan, the Opus coder left 0.18 fewer real defects per review than the Sonnet coder, clear of the noise band of 0.16. Hidden-test failures were 0.09 lower, inside the noise band. Without a plan, Opus failed 1.21 fewer hidden tests per task and left 2.5 fewer real defects per review. Raw coder tokens per dispatch fell about a third with a plan, median 424k against 633k, and cache reads fell by half. The trade: an Opus token counts for more against the usage limits, by a ratio that is not published, and coding holds about 30% of work tokens, nearly all Sonnet before this change. The Opus-pinned deep coder is now the same model as the coder. Live check: the work census before and after, for coding tokens by model and type, and review-loop fix rounds per phase.

## Watch

—

## Back-out

set the model line back to sonnet.
