---
type: "Change"
title: "The telemetry report's scan step dropped its recall measurement and now names only the two scans that still"
description: "The telemetry report's scan step dropped its recall measurement and now names only the two scans that still run."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 5
components: ["skill/audit"]
evidence: ["census"]
watches: []
---

## Change

The telemetry report's scan step dropped its recall measurement and now names only the two scans that still run

## Evidence

census

## Result

Three whole-tree sweeps — copied blocks, diverged copies, unreferenced symbols — were retired from the loop earlier, but the report still described a recall figure computed from a field only they justified, and that field has never been populated on a single row. The step now reports precision for the two scans that actually run and treats the retired sweeps' rows as history rather than a current rate. The field's own documentation in the two logging scripts is still stale and needs the same trim.

## Watch

—

## Back-out

—
