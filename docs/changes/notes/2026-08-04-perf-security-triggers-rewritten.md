---
type: "Change"
change_type: "changed"
title: "The `perf` and `security` reviewers now trigger on corrected conditions"
description: "The conditions that start the `perf` and `security` reviewers were rewritten after they fired falsely; the reviewers themselves are unchanged."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["agent/review-loop", "agent/perf-reviewer", "agent/security-reviewer"]
evidence: ["false positives"]
watches: []
---

## Change

The `perf` and `security` reviewers now start on rewritten trigger conditions. The reviewers are untouched; only their triggers were wrong.

## Evidence

false positives

## Result

Gates untouched; only their triggers were wrong

## Watch

—

## Back-out

—
