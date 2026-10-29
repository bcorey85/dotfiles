---
type: "Change"
change_type: "removed"
title: "The review telemetry's comment-noise count is retired: the review loop still writes the field as 0 on every"
description: "The review telemetry's comment-noise count is retired: the review loop still writes the field as 0 on every row for schema stability, and the audit skill no longer computes or reads it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review telemetry's comment-noise count is retired: the review loop still writes the field as 0 on every row for schema stability, and the audit skill no longer computes or reads it.

## Evidence

census

## Result

The count was 0 on every logged run that carried the field and absent on the rest, across all 34 runs in the metrics log, so the reviewer instruction that fed it never produced a deletion. That instruction left the diff reviewer with the judgment text, and a sensor that never fired is not moved to another reviewer.

## Watch

—

## Back-out

—
