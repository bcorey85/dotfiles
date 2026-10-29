---
type: "Change"
change_type: "changed"
title: "The test-intent reviewer's weak-assertion sweep now owes a count"
description: "The test-intent reviewer's weak-assertion sweep now owes a count: the absence pass names what to enumerate (success-criterion lines, named contract values and fallbacks, edge-case rows), greps the suite per promise, and reports `Promises walked: N, unpinned: M` in the header, always."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/test-intent-reviewer"]
evidence: ["seeded round"]
watches: []
---

## Change

The test-intent reviewer's weak-assertion sweep now owes a count: the absence pass names what to enumerate (success-criterion lines, named contract values and fallbacks, edge-case rows), greps the suite per promise, and reports `Promises walked: N, unpinned: M` in the header, always. The report header carries that line.

## Evidence

seeded round

### Anchor reasons

Anchor `agents/test-intent-reviewer.md`, section `## Step 5 — Weak-assertion sweep (branch-added tests, whole-suite scope)` (evidence: removal round, seeded round):

The weak-test definition, the shape pass, the absence pass with its required `Promises walked: N, unpinned: M` count, the no-citation-means-unverifiable rule, and the test-writer route. The six named weak shapes are gone: all six planted shapes were flagged in every run without them. The required count is what makes the absence pass run: with no count required, a planted plan promise with no test went unfound in every run of both the long and the short text; with the count required it was found in every run, at about a quarter more reviewer tokens. The route is now the fix skill, since the test writer is gone. Renumbered from Step 6 when the coverage-net step went: it found 0 losses in 15 work audits.

## Result

One plan promise with no pinning test, planted at the branch point of the cull-half tree. Without the required count, the reviewer found it in none of six runs across the long and the short text, and no report mentioned a promise walk. With the count required, three of three runs found it, named the same missing assertion with the plan line, and every other planted defect was found as before. Reviewer tokens on the cull half rose by about a quarter, still a quarter under the long text.

## Watch

—

## Back-out

—
