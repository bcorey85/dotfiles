---
type: "Change"
change_type: "fixed"
title: "Two text corrections in the test-intent reviewer: the ticket filename is `00-ticket.md`"
description: "Two text corrections in the test-intent reviewer: the ticket filename is `00-ticket.md`, the name the resolver writes, and the two cull-only header lines say \"cull half only\" so the bug-pinning half no longer owes them."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 5
kind: "fix"
components: ["agent/test-intent-reviewer"]
evidence: ["judgment"]
watches: []
---

## Change

Two text corrections in the test-intent reviewer: the ticket filename is `00-ticket.md`, the name the resolver writes, and the two cull-only header lines say "cull half only" so the bug-pinning half no longer owes them.

## Evidence

judgment

### Anchor reasons

Anchor `agents/test-intent-reviewer.md`, section `## Step 1 — Resolve the intent oracle` (evidence: removal round, judgment):

The resolver call, the oracle priority (ticket, then success criteria, plan mechanics demoted), the three exit codes, and the oracle-strength tag. Kept verbatim; every run in both arms resolved the oracle and tagged findings spec-backed. The ticket filename is `00-ticket.md`, the resolver's real name, by judgment.

## Result

Both arms of the removal round found the ticket under the wrong name, and both omitted the cull-only header line in the bug-pinning half. Neither correction moved any planted defect in the seeded round that followed.

## Watch

—

## Back-out

—
