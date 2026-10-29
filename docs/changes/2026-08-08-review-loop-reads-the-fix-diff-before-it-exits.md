---
type: "Change"
change_type: "changed"
title: "Review loop reads the fix diff before it exits"
description: "Review loop reads the fix diff before it exits."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["seeded round"]
watches: []
---

## Change

Review loop reads the fix diff before it exits

## Evidence

seeded round

## Result

Fixes were never re-read; the pass recovers real defects introduced by the fix itself, at no measurable added cost

## Watch

—

## Back-out

—
