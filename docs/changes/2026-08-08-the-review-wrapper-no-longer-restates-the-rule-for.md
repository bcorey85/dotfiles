---
type: "Change"
title: "The review wrapper no longer restates the rule for classifying a finding that invalidates a plan"
description: "The review wrapper no longer restates the rule for classifying a finding that invalidates a plan, and points at the agent that owns it instead."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 18
components: ["skill/review"]
evidence: ["census"]
watches: []
---

## Change

The review wrapper no longer restates the rule for classifying a finding that invalidates a plan, and points at the agent that owns it instead

## Evidence

census

### Anchor reasons

Anchor `skills/review/SKILL.md`, section `## Plan-impact findings (unskippable routing)` (evidence: removal round):

The four steps: never fold it in, raise the modal with the three options before any dispatch, record the answer in the plan's deviations section, re-dispatch with both counters. The "modal blocks until answered" and the verify/adr cross-references are gone: every run surfaced the plan-impact packet with its three options and dispatched nothing else without them.

## Result

The two copies had already drifted, and the wrapper's had lost the qualifier limiting the category to a missed external contract — without it, ordinary internal defects route into a modal that blocks until a human answers

## Watch

—

## Back-out

—
