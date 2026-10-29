---
type: "Change"
change_type: "changed"
title: "A reviewer finding whose substance is that the code and a plan, ADR"
description: "A reviewer finding whose substance is that the code and a plan, ADR, or acceptance criterion disagree now has a mechanical route: decide which document is wrong, then either a plain fix naming the clause the code must match."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["agent/code-reviewer", "agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

A reviewer finding whose substance is that the code and a plan, ADR, or acceptance criterion disagree now has a mechanical route: decide which document is wrong, then either a plain fix naming the clause the code must match, or a finding text opening with the literal escalation prefix the loop scans for

## Evidence

census

### Anchor reasons

Anchor `agents/spec-leak-check.md`, section `## Rules` (evidence: unproven):

Write nothing, verdict only; a state-shaped question that survives rewriting is clean even when suggestive; never speculate about what is being built. The restraint clause here is the guard against a tripwire that flags everything, and nothing has measured its false-positive rate.

## Result

The rule that a plan contradiction is not a question was already written and was being followed in judgment but not in labeling — plan-drift was the largest single group in the question pile, and the near-misses in it read "candidate", "owner call needed", or ended in a question mark, none of which the loop's scan matches. A question that never reaches the escalation path arrives to a human as one more triage line instead of the decision it is.

## Watch

—

## Back-out

—
