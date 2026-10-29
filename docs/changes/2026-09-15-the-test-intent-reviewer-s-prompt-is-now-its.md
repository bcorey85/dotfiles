---
type: "Change"
change_type: "changed"
title: "The test-intent reviewer's prompt is now its contract only"
description: "The test-intent reviewer's prompt is now its contract only: the boxed question with a one-sentence definition of a pinned bug, the oracle resolution with its exit codes, the two dispatch halves, the three audit labels, the cull question with the read-only mutation fence."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/test-intent-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The test-intent reviewer's prompt is now its contract only: the boxed question with a one-sentence definition of a pinned bug, the oracle resolution with its exit codes, the two dispatch halves, the three audit labels, the cull question with the read-only mutation fence, the coverage-net check with the denominator rule and two exemptions, the plan-promise sweep with the no-citation rule, and the report block. Gone: the separate core-rule section, the one-sided-pin paragraph, the six snapshot smells, the named cull shapes and the "diff noise" sentence, the "coverage often moves" sentence, the six named weak shapes, the boundary section, and the guidelines. About 1,350 words loaded per invocation instead of about 2,060.

## Evidence

removal round

### Anchor reasons

Anchor `agents/test-intent-reviewer.md`, section `(preamble)` (evidence: removal round, census, judgment):

Dispatch contract: name, description, the opus pin, the read-only tool list, the boxed question, and the one-sentence definition of a pinned bug with the read-the-implementation-for-what-not-whether rule folded in. The separate "core rule" section, the one-sided-pin paragraph, and the six snapshot smells are gone: the contract-only text found every planted bug-pin and cull in every run that the full text did, with no new false positives. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home.

Anchor `agents/test-intent-reviewer.md`, section `## Step 2 — Scope to changed tests only` (evidence: removal round):

Changed files only, and the two dispatch halves with the run-both fallback. Kept verbatim; no run in either arm reported findings from the half it was not sent. By judgment, the cull half runs Steps 4 and 5, since the coverage-net step is gone.

Anchor `agents/test-intent-reviewer.md`, section `## Step 3 — Audit each assertion against the oracle` (evidence: removal round):

The three labels: pins intent, pins bug, unverifiable. The list of cull shapes and the "diff noise" sentence that followed are gone: equal on every planted bug-pin, and the decoy tests were not flagged in either text after audit.

Anchor `agents/test-intent-reviewer.md`, section `## Step 4 — Cull check (added tests only)` (evidence: removal round):

The one cull question, the read-only mutation fence with its route to the mutation tester, the one-smoke-test exemption, and the coverage-gap boundary. The named cull shapes are gone: equal on all three planted duplicates.

## Result

Three Opus runs per arm on each of two seeded trees, one with five pinned bugs and decoys for the bug-pinning half, one with duplicate, deleted, and weak tests for the cull half. The contract text found every planted defect the full text found, in every run, with no false positive after audit and no finding from the half it was not sent. Opus tokens fell by a third on the cull half and rose by a quarter on the bug-pinning half, the rise being cache reads from one to three extra greps; pooled over both halves the contract text used 13 percent fewer. Neither text found the planted plan promise that no test pins.

## Watch

—

## Back-out

—
