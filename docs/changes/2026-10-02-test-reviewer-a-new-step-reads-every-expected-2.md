---
type: "Change"
change_type: "changed"
title: "test-reviewer now checks every expected value a test pins against the acceptance criteria, ticket and plan"
description: "test-reviewer: a new step reads every expected value a test pins against the acceptance criteria, ticket and plan, with the criteria outranking the ticket and plan."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/test-reviewer", "skill/fix"]
evidence: ["reviewer replay"]
watches: []
---

## Change

test-reviewer: a new step reads every expected value a test pins against the acceptance criteria, ticket and plan, with the criteria outranking the ticket and plan. An assertion they contradict is a `fix` (change it to what they say); a detail they all leave open is an `ask` and the assertion stays. New report section for these findings

## Evidence

reviewer replay

### Anchor reasons

Anchor `agents/test-reviewer.md`, section `## Review Process` (evidence: removal round, reviewer replay):

One paragraph per step: map, gaps with the must-test rule, the weak/brittle/stale/missing classes, hygiene, and the cull rule with its exemptions. The pattern bullets and the four cull shapes are gone: every plant was found in every run without them, and the reviewer named its own shapes for each cull candidate. A new step reads every expected value that a test pins against the acceptance criteria, the ticket and the plan, with the criteria first. A value that they contradict is a fix, and a detail that they all leave open is a question. Reviewer replay on five finished trees used criteria written from the ticket plus a decision ledger. The trees hold 21 tests that agree with the code but fail on a reference implementation. The old text flagged 17 of them, 14 as fixes. The new text flagged 20, 17 as fixes. Neither told the coder to weaken a correct test. The cost per review was 13% more Opus output and about 4 s.

## Result

Replayed on five finished trees with criteria written the way work writes them, from the ticket plus a decision ledger. The trees hold 21 tests that agree with the code but fail on a reference implementation. The old reviewer flagged 17, 14 as fixes; the new one flagged 20, 17 as fixes. The 3 extra fixes all sit in one tree: a token past its rotation grace asserted as "revoked" where the criteria say "expired". Neither told the coder to weaken a correct test. Cost per review: Opus output +13% (6409 vs 5653 tokens), about 4 s more. The larger gain was in the criteria: on criteria written from the ticket alone, the old reviewer flagged only 2 of the 21

## Watch

—

## Back-out

—
