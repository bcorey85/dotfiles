---
type: "Change"
title: "Review loop: one fix coder takes every `fix` finding, test gaps included"
description: "Review loop: one fix coder takes every `fix` finding, test gaps included."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 13
components: ["agent/review-loop", "skill/fix", "agent/test-writer", "agent/test-reviewer"]
evidence: ["bench smoke"]
watches: []
---

## Change

Review loop: one fix coder takes every `fix` finding, test gaps included. No test-writer runs in the loop. The test reviewer still files the gaps

## Evidence

bench smoke

## Result

One pair on one ticket, phases 0 to 6, against the loop that sends test gaps to a test-writer. Quality equal: 17 of 19 seeded bugs caught both ways, 19 of 19 hidden checks pass both ways, structure check clean both ways. Agent time 81 min against 122 min (−34%). Cost $26.00 against $27.63 (−6%): Opus −27%, Sonnet +94%. Test lines 2,798 against 5,446. One pair only, so the speed and cost gaps are not proven against run-to-run spread. Work logs cannot size it.

## Watch

—

## Back-out

restore `agents/review-loop.md` from git
