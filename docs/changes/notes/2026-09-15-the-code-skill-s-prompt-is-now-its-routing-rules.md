---
type: "Change"
change_type: "changed"
title: "The code skill's prompt now holds its routing rules only, loading about 1,570 words instead of about 2,990"
description: "The code skill's prompt is now its routing rules only: the task-input resolution, the modifier pointer, phase-scoped plan reading, the acceptance-criteria stop, one coder then the test-writer per phase, the plan-impact modal, the handoff block, the review-loop dispatch and its status routing."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["shared/plan-reading", "agent/test-writer", "shared/handoff-block", "agent/review-loop"]
evidence: ["removal round"]
watches: []
---

## Change

The code skill's prompt is now its routing rules only: the task-input resolution, the modifier pointer, phase-scoped plan reading, the acceptance-criteria stop, one coder then the test-writer per phase, the plan-impact modal, the handoff block, the review-loop dispatch and its status routing, the phase-line flip, the phase-boundary decision, the three phase-complete blocks, and the stage-queue walkthrough. Gone: the rationale sentences, the restated schemas, the negatives ("do not skill-invoke review", "never by whole file", "do not rank files yourself"), the placeholder notes, and the walkthrough fences. Two rules moved instead of going: the clean gate mark is now the first sentence of the converged branch, and the cap branch keeps the sentence that the dirty session is what keeps the commit blocked. About 1,570 words loaded per invocation instead of about 2,990.

## Evidence

removal round

### Anchor reasons

Anchor `agents/review-loop.md`, section `# Review Loop` (evidence: removal round, judgment):

The role: own the review-fix loop and return one packet, with no modal tool. Byte-identical in both arms of the removal round, so not itself varied. Cut by judgment since: the isolated-context aside and the sentence calling the caller a thin wrapper. Neither changes what the agent does.

## Result

Two rounds of three Sonnet runs per arm on four plan trees, with the coder, test-writer, and review loop replaced by stand-ins that return fixed reports so only the orchestrator varies. The routing-only text dispatched the same agents in the same order with the same parameters, stopped on missing criteria, stopped on a capped loop, and raised the plan-impact question at the earlier text's rate, at seven percent fewer orchestrator tokens on a clean phase. The first cut lost two rules that sat after "present the asks and wait": with an empty ask list the orchestrator skipped the gate mark in every run and marked a capped phase done in every run. Moving the gate mark to the head of the branch fixed the first in every run (the earlier text managed two of three); restoring the commit-blocked sentence brought the second back to the earlier text's one miss in three. That remaining miss, in both texts, is the orchestrator re-judging the loop's last finding as a false positive and marking the phase done. One run of the new text ignored the coder's plan-impact block outright; the earlier text raised it in all three.

## Watch

—

## Back-out

—
