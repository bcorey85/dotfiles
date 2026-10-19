---
type: "Change"
title: "The architect core's Refactor Candidates placeholder is one line now"
description: "The architect core's Refactor Candidates placeholder is one line now: pre-existing areas worth a separate refactor, or none (8 words from 50, 306 remain in the core)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 13
components: ["skill/architect-core"]
evidence: ["removal round"]
watches: []
---

## Change

The architect core's Refactor Candidates placeholder is one line now: pre-existing areas worth a separate refactor, or none (8 words from 50, 306 remain in the core). Gone: the smell threshold, the four fields for each item, the ranked-and-capped rule, and the never-manufacture sentence. Both architects load this file.

## Evidence

removal round

### Anchor reasons

Anchor `skills/architect-core/SKILL.md`, section `(preamble)` (evidence: census):

Frontmatter: the name that both architects preload by, and the description. Kept in both texts of the removal round.

Anchor `skills/architect-core/SKILL.md`, section `# Architect Core Directives` (evidence: unproven):

The pointer to what the agent file adds on top, and the role line: design only, read-only, a plan that the coder builds without a guess. Unproven: with the role line removed, every Opus backend architect still left the tree unchanged, and the agent holds no edit tool. The line stays because the frontend architect preloads this block too, and it never ran. The words that name the plan-spec list and the edge cases stay with those two blocks, and both blocks still exist.

Anchor `skills/architect-core/SKILL.md`, section `## Output Format` (evidence: census, removal round):

The plan envelope: overview, body, steps, edge cases, and the closing trio. Seven toolkit files read the Success Criteria heading, and both architect files name the trio. Every Opus plan held the full envelope under both texts. The Refactor Candidates placeholder is one line now: without the smell threshold, the four fields, and the cap, all but one refactor item still named a file. The plans listed about twice as many items at about 40% fewer words each, and no plan said that nothing crossed the bar. No toolkit file parses the four fields. Only the backend architect ran.

## Result

Without the text, all but one refactor item still named a file, and no toolkit file parses the four fields. The text did cap the list: plans without it held about twice as many items, each about 40% shorter, and no plan said that nothing crossed the bar, where a third of the plans with the text did. The section still came out shorter without the text, so the edit costs no plan words. It costs about one more short item to read in each plan. Only the backend architect ran, so the effect on the frontend architect rests on the shared text alone.

## Watch

—

## Back-out

—
