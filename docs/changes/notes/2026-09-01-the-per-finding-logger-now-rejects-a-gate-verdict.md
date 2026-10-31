---
type: "Change"
change_type: "changed"
title: "The per-finding logger now rejects a gate verdict outside its three legal values"
description: "The per-finding logger now rejects a gate verdict outside its three legal values, and the telemetry report folds the historical bad ones into a single no-verdict-recorded bucket."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 12
kind: "behavior"
components: ["script/log-review-finding", "skill/audit"]
evidence: ["census"]
watches: []
---

## Change

The per-finding logger now rejects a gate verdict outside its three legal values, and the telemetry report folds the historical bad ones into a single no-verdict-recorded bucket

## Evidence

census

## Result

About one run row in thirteen carried a disposition word in the verdict field — "fix", "clean", "gaps", "actioned" — each landing as a bucket of size one that reads as a verdict the gate never gave. The field is reported as a distribution, so a dozen singleton buckets is exactly the shape that makes it unreadable. Free text has a field already.

## Watch

—

## Back-out

—
