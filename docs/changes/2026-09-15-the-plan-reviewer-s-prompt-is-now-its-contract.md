---
type: "Change"
title: "The plan reviewer's prompt is now its contract only: the boxed question, the inputs"
description: "The plan reviewer's prompt is now its contract only: the boxed question, the inputs, one paragraph per finding class (tree claims with citation resolution and settle-every-check-in-one-turn, dangling dependencies, contract disagreement, uncovered ticket requirements, two-reading instructions."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 6
components: ["agent/plan-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The plan reviewer's prompt is now its contract only: the boxed question, the inputs, one paragraph per finding class (tree claims with citation resolution and settle-every-check-in-one-turn, dangling dependencies, contract disagreement, uncovered ticket requirements, two-reading instructions, criteria that cannot fail, ordering that cannot hold, an approach that cannot work, an approach not to take), re-entry, the enumerate-never-sample rule, the alternative bar as one sentence, the evidence-class rule, the not-yours list, and the output block. Gone: the first-reader paragraph, the bullets under tree claims, the rubber-duck prose, the settled-decisions line, the alternative bar's bullets and "Consider using X" sentence, the second zero-ALT copy, and the closing invented-finding paragraph. About 880 words loaded per invocation instead of about 1,560.

## Evidence

removal round

### Anchor reasons

Anchor `agents/plan-reviewer.md`, section `## Your inputs` (evidence: removal round):

Read the dispatched paths from disk, read the codebase for assumed-exists claims, never the ledger or research unless named. Kept verbatim; every run in both arms read the plan, the ticket, and the tree.

Anchor `agents/plan-reviewer.md`, section `## The bar for an alternative` (evidence: removal round):

One sentence: what changes, what disappears, what it costs, why the authors missed it, and zero ALT is correct. The four bullets, the "Consider using X" sentence, and the second zero-ALT copy are gone: no in-tree alternative was lost. The contract text wrote no ALT where the full text wrote corpus-driven ones; whether it suppresses in-tree alternatives is untested.

Anchor `agents/plan-reviewer.md`, section `## The bar for a mechanism you propose` (evidence: removal round):

The `Evidence-class:` line, exercised or declared-only, never omitted. Kept verbatim.

Anchor `agents/plan-reviewer.md`, section `## What is not yours` (evidence: removal round):

Argue, never redesign; no code quality, security, or performance. Kept verbatim; no run in either arm wrote to the tree or reviewed code.

Anchor `agents/plan-reviewer.md`, section `## Output` (evidence: removal round):

The DUCK-first report block, the four severity definitions, and the VERDICT line. The closing "invented-finding pass is worse" paragraph is gone: zero invented findings on the unmodified plan in either arm without it.

Anchor `agents/goal-blind-researcher.md`, section `## Dispatch inputs` (evidence: unproven):

The two required inputs and the stop-and-name-which behavior when one is missing. Never varied.

## Result

Three Opus runs per arm on a seeded plan with one plant per finding class and three per arm on the unmodified plan. The contract text found every plant the full text found, in every run, invented no finding on the unmodified plan, and reported more real in-tree defects. It stopped scanning the live transcript corpus the plan cites, which is where the full text spent most of its tool calls. Opus fresh and output tokens fell by about a quarter and cache reads by about 60 percent per review. It wrote no alternative in six runs where the full text wrote five, all of them corpus-driven.

## Watch

—

## Back-out

—
