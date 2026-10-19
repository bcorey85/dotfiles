---
type: "Change"
title: "The audit lane gained a per-class recall step: the caught log joined to the escape log on their shared class"
description: "The audit lane gained a per-class recall step: the caught log joined to the escape log on their shared class column, with rules for attributing a miss only to a gate that could have caught it, for treating zero escapes as unmeasured rather than perfect."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 14
components: ["skill/audit"]
evidence: ["census"]
watches: []
---

## Change

The audit lane gained a per-class recall step: the caught log joined to the escape log on their shared class column, with rules for attributing a miss only to a gate that could have caught it, for treating zero escapes as unmeasured rather than perfect, and for refusing to score a gate whose domain has no class value

## Evidence

census

## Result

Every number in the lane counted what the gates found; none counted what they missed, so a gate nobody points at was indistinguishable from a gate that catches everything. The join was possible all along — the two logs were built to share a vocabulary — and running it moved the leak from the thin specialists to the most-exercised gate in the loop.

## Watch

—

## Back-out

—
