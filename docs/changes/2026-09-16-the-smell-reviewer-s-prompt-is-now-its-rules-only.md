---
type: "Change"
change_type: "changed"
title: "The smell reviewer's prompt now holds its rules only"
description: "The smell reviewer's prompt is now its rules only: the calibration read, the five scope items with the prior-art search and the shared-decision rule, the defensive-scaffolding test, the dead-export reference search, disposition by consequence, the anti-churn line, the bound paragraph."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-16T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/smell-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The smell reviewer's prompt is now its rules only: the calibration read, the five scope items with the prior-art search and the shared-decision rule, the defensive-scaffolding test, the dead-export reference search, disposition by consequence, the anti-churn line, the bound paragraph, the format and design-decision threshold, the deferrals with the closing-note rule, the four process steps, and the output block. Gone: the sentences that explained why each rule exists (the author's structural blind spot, size does not excuse a copied formula, defensive scaffolding as the agentic form, the `export` keyword hiding a death, premature abstraction versus duplication, blast radius as a fact not an escalation, structure does not stop a phase).

## Evidence

removal round

### Anchor reasons

Anchor `agents/smell-reviewer.md`, section `## Your scope — ONLY these, and ONLY inside your dispatched bound` (evidence: removal round, seeded round):

The five scope items with the prior-art search and the shared-decision rule, the defensive-scaffolding test, the dead-export reference search, disposition by consequence, the anti-churn line, and the bound paragraph. The rationale sentences (the author's blind spot, size does not excuse it, defensive scaffolding is the agentic form, the `export` keyword hides a death, premature abstraction, structure does not stop a phase, a candidate you can't name) are gone: on a seeded diff with one plant per scope item, the reviewer found all six in every run with the same dispositions and the same cited searches without them, and filed no invented finding on the clean twin. The review loop's bound is now the diff under first review, not a converged phase diff. The loop now sends the structure reviewer beside the first review. In a seeded round on five large diffs, three runs each, the review caught 45 of 45 planted structure defects with it. Without it, the review caught 39 of 45.

Anchor `agents/smell-reviewer.md`, section `## Format (required)` (evidence: removal round):

The `[smell]` prefix, the `[design-decision]` routing tag, and its threshold sentence. The "blast radius is a fact to state" and "look for the shape that preserves every guarantee" sentences are gone: no run in either arm raised a design-decision tag on either tree.

Anchor `agents/smell-reviewer.md`, section `## Process` (evidence: removal round):

The four steps: scope, prior-art pass, dead-reference pass, project CLAUDE.md. Byte-identical in both arms.

Anchor `agents/smell-reviewer.md`, section `## Output Format` (evidence: removal round):

The summary block with Fix, Ask, and Nit. Byte-identical in both arms.

## Result

A seeded feature diff on a Go CLI with six smells, one per scope item (a re-implemented formatter with a different rounding, a sentinel copied at three sites, aggregation in the CLI layer, a name off the sibling vocabulary, an options type nothing passes, an export nothing calls), three decoys the reviewer must suppress, and a clean twin of the same feature. Three runs per arm per tree on Opus, the tier the loop runs it on. Both wordings found all six plants in every run with the same dispositions and a cited search for every prior-art and dead-export verdict, filed no decoy, and raised exactly one finding on the clean twin in every run, a real duplication the seeding did not intend. Reviewer Opus fresh+output tokens 0.95x; wall and turns unchanged.

## Watch

—

## Back-out

—
