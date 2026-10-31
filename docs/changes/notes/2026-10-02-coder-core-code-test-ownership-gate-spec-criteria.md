---
type: "Change"
change_type: "changed"
title: "The coder now writes its own tests from the plan and acceptance criteria, and `/code` dispatches no separate test-writer"
description: "The coder writes the tests for the behavior it implements, asserting what the plan and acceptance criteria state, and fixes the code, never the assertion, when a supported test is red."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["skill/coder-core", "skill/code", "agent/spec-criteria", "script/spec-criteria-lint", "shared/plan-format", "skill/eng-spec", "agent/test-writer", "agent/review-loop", "agent/test-reviewer", "agent/code-reviewer"]
evidence: ["sealed round", "reviewer replay"]
watches: ["coder-writes-own-tests"]
---

## Change

The coder writes the tests for the behavior it implements, asserting what the plan and acceptance criteria state, and fixes the code, never the assertion, when a supported test is red. `/code` no longer dispatches a test-writer after the coder; `tests-run` comes from the coder's report. The test-file hook binds no agent type, plans list test files as File targets, and the lint checks that flagged test files in a plan are gone. The review loop still runs the test reviewer beside the code reviewer, and still sends test-gap fixes to a test-writer

## Evidence

sealed round, reviewer replay

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Tests are yours` (evidence: sealed round, reviewer replay, removal round, judgment):

The coder writes the tests for the behavior it implements, in the project's test layout. Ticket numbers are no longer in its vocabulary ban, by judgment. It asserts what the plan and the acceptance criteria state, and it fixes the code, never the assertion, when a supported test is red. In a sealed round of 72 valid runs on ticket-level cells, the new flow had 0.25 hidden failures per run, against 0.42. The old flow sent a test writer after the coder. The gap is inside two standard errors. The new flow was about 20% faster and used about two-thirds more Opus cache read per run. The new flow was held at first, because the coder's own tests locked in a behavior that the ticket forbids. Those criteria came from the ticket alone. In a reviewer replay with criteria written from the ticket plus a decision ledger, the test reviewer flagged 17 to 20 of 21 such tests. Kept from the earlier text, which stood in a removal round: the rule to report an existing test that turns red, acceptance criteria as spec, and the one-sentence vocabulary ban. The criteria sentence stays by judgment. By judgment on a census of work test audits, which culled 53 tests in 15 audits: before it keeps a test, the coder names the bug that test alone would catch, and deletes a duplicate or a test of a mock, the framework or a restated implementation. Effect unmeasured. The sentence that told the coder to run its tests is gone, because the verify block now says who runs the checks. Same sealed round as the phase-scoped read block.

Anchor `agents/spec-criteria.md`, section `## Dispatch inputs` (evidence: unproven):

The three inputs and the go-lean fallback when the decision ledger is absent. Never varied.

Anchor `agents/spec-criteria.md`, section `## What a criterion is` (evidence: unproven):

One observable sentence in the user's words, with the good and bad example that sets the line between a criterion and a test, and the rule that a ticket/plan divergence is written the ticket's way and flagged. The examples are the kind of text that measured inert in two other reviewers; nothing has checked them here.

Anchor `agents/spec-criteria.md`, section `## Return` (evidence: unproven):

The return block with counts, the open ticket-owner questions, and the divergences section. Never varied.

## Result

Sealed bench comparison on ticket-level cells, 72 valid runs: hidden failures per run 0.25 vs 0.42 for the coder-then-test-writer flow (gap inside 2 SE), about 20% faster on wall-clock with the specialist pass matched, about two-thirds more Opus cache read per run. It was held at first because the coder's own tests locked in a behavior the ticket forbids; that lock-in came from criteria written from the ticket alone. With criteria written from the ticket plus a decision ledger, the test reviewer flagged 17 to 20 of 21 such tests. Check after the edit: escapes with `stage_found` past review and test-gap findings per loop in the work logs

## Watch

Read 2026-10-24 on work logs through 2026-10-21: test-gap findings per code-reviewer run fell from a median of 0.38 (range 0.22 to 0.51) to 0.19. Better. Kept. Watch closed.

## Back-out

—
