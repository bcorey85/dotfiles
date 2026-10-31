---
type: "Change"
change_type: "changed"
title: "The telemetry report's scan step now names only the two scans that still run"
description: "The telemetry report's scan step now names only the two scans that still run and no longer measures recall."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["skill/audit"]
evidence: ["census"]
watches: []
---

## Change

The telemetry report's scan step now names only the two scans that still run and no longer measures recall

## Evidence

census

## Result

Three whole-tree sweeps — copied blocks, diverged copies, unreferenced symbols — were retired from the loop earlier, but the report still described a recall figure computed from a field only they justified, and that field has never been populated on a single row. The step now reports precision for the two scans that actually run and treats the retired sweeps' rows as history rather than a current rate. The field's own documentation in the two logging scripts is still stale and needs the same trim.

## Watch

—

## Back-out

—
