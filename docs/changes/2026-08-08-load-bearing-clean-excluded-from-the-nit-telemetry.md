---
type: "Change"
title: "`load_bearing_clean` excluded from the `nit` telemetry count"
description: "`load_bearing_clean` excluded from the `nit` telemetry count."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 9
components: ["script/log-review-metrics"]
evidence: ["field audit"]
watches: []
---

## Change

`load_bearing_clean` excluded from the `nit` telemetry count

## Evidence

field audit

## Result

A packet reporting 1 nit logged `nit:2`; the extra was the clean-file flag. It inflated the field measuring reviewer noise **when a gate came back clean** — the tuning signal pointed the wrong way

## Watch

—

## Back-out

—
