---
type: "Change"
change_type: "changed"
title: "review-loop: specialist reviewers (security, perf, structure) run beside the first code review and share one fix pass"
description: "review-loop: the eligible specialist reviewers (security, perf, structure) run beside the first code review instead of after convergence, and their findings share one fix pass."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/review-loop", "agent/test-writer"]
evidence: ["seeded bench"]
watches: []
---

## Change

review-loop: the eligible specialist reviewers (security, perf, structure) run beside the first code review instead of after convergence, and their findings share one fix pass. Test-gap findings go to a Sonnet test-writer dispatched beside the fix coder; the fix coder never edits a test file

## Evidence

seeded bench

## Result

On two seeded trees, median priced loop time fell from 1362 s to 1082 s and from 1362 s to 778 s. Every treated loop beat the typical old loop. Seeds caught tied, and unfixed findings at exit fell from 2 to 0 per loop on both trees. Tokens: the larger tree used more (Opus cache read +22%, Sonnet +43%, mostly test-writer runs that close gaps the old loop left open); the smaller tree cut Opus cache read 77%. Applies to the 36% of work loops that run a specialist. Check after the edit: unfixed findings at exit and loop wall-clock in the work review metrics

## Watch

—

## Back-out

—
