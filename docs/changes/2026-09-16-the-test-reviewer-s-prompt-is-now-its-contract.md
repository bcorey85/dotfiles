---
type: "Change"
change_type: "changed"
title: "The test reviewer's prompt is now its contract only: the role line with the mission folded in"
description: "The test reviewer's prompt is now its contract only: the role line with the mission folded in, the calibration section, the four target scopes with the branch diff command, one paragraph per review step (map, gaps with the must-test rule, weak/brittle/stale/missing classes, hygiene)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-16T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/test-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The test reviewer's prompt is now its contract only: the role line with the mission folded in, the calibration section, the four target scopes with the branch diff command, one paragraph per review step (map, gaps with the must-test rule, weak/brittle/stale/missing classes, hygiene), the cull rule with its exemptions, and the output block. Gone: the mission heading, every pattern bullet under the gap, weakness, and hygiene steps, the four cull shapes, and the six closing guidelines. About 810 words loaded per invocation instead of about 1,210.

## Evidence

removal round

### Anchor reasons

Anchor `agents/test-reviewer.md`, section `(preamble)` (evidence: removal round, census, judgment, seeded round):

Dispatch contract: name, description, the opus pin, the read-only tool list, and the role line with the mission folded in. The Primary Mission heading is gone: equal on every planted gap, weak test, and cull candidate without it. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home. The description now names the review loop as a dispatcher. The loop sends this reviewer beside the first review on a large diff with test files. That shape comes from a seeded round on one 814-line diff, five runs each. The review found 15 of 15 test gaps with this reviewer, against 10 of 15 without it.

Anchor `agents/test-reviewer.md`, section `## Calibration — restraint over thoroughness` (evidence: removal round):

The schedule-work test, never demote a gap to nit, the hedging rule, and the silent-regression bar. Kept verbatim; the six closing guidelines that restated it are gone with no change in findings or decoy flags.

Anchor `agents/test-reviewer.md`, section `## Target Scope` (evidence: removal round):

The four scopes and the branch diff command. Kept verbatim; every branch-scope run in both arms ran the diff and reviewed exactly the four files it listed.

## Result

Three Opus runs per arm on a module-scope tree with three deleted tests and one gutted assertion, and three per arm on a branch-scope tree with three cull candidates, six weak added tests, and one deleted test. The contract text found every plant the full text found, in every run of both trees, and flagged the same one sound consolidation as a nit. Finding counts did not rise without the bullets. Opus fresh and output tokens fell 5 percent and cache reads 17 percent; wall-clock and tool calls did not move. The gain is prompt size, not speed.

## Watch

—

## Back-out

—
