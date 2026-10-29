---
type: "Change"
change_type: "changed"
title: "The `nit` telemetry count now ignores the clean-file flag"
description: "The `nit` count in review telemetry no longer includes `load_bearing_clean`, so a packet reporting 1 nit logs `nit:1` instead of `nit:2`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 9
kind: "behavior"
components: ["script/log-review-metrics"]
evidence: ["field audit"]
watches: []
---

## Change

The `nit` telemetry count no longer includes the `load_bearing_clean` flag, so the field measures reviewer noise correctly when a gate comes back clean.

## Evidence

field audit

## Result

A packet reporting 1 nit logged `nit:2`; the extra was the clean-file flag. It inflated the field measuring reviewer noise **when a gate came back clean** — the tuning signal pointed the wrong way

## Watch

—

## Back-out

—
