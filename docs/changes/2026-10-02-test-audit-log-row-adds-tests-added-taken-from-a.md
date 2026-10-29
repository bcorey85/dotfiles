---
type: "Change"
change_type: "changed"
title: "Test audit log row: adds `tests_added`, taken from a new tests-added header line in the test-intent"
description: "Test audit log row: adds `tests_added`, taken from a new tests-added header line in the test-intent reviewer's cull report."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 16
kind: "behavior"
components: ["skill/test-audit", "agent/test-intent-reviewer"]
evidence: ["judgment"]
watches: []
---

## Change

Test audit log row: adds `tests_added`, taken from a new tests-added header line in the test-intent reviewer's cull report

## Evidence

judgment

### Anchor reasons

Anchor `agents/test-intent-reviewer.md`, section `## Output Format` (evidence: removal round, seeded round):

The report block the dispatcher relays and the scorer reads, with the base-suite and promises-walked header lines marked cull half only. The boundary section and the guidelines that sat around it are gone: equal on every plant, and no run in either arm wrote to the tree. The promises line is the output the absence pass owes; see Step 6. The base-suite header line and the lost-coverage section are gone with the coverage-net step, which found 0 losses in 15 work audits. By judgment, the cull half reports a tests-added count, so the test audit's log row has a base for its cull and weak counts.

## Result

The cull and weak counts per audit (53 culls and 67 weak over 15 work audits) have no base, so a high count cannot be told from a large branch. Instrument only; it changes no finding.

## Watch

—

## Back-out

restore the two agent copies and the test-audit skill from git
