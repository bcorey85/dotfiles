---
type: "Change"
change_type: "changed"
title: "`log-scan`'s `exit=` redefined as did-it-RUN (0 = printed rows, 1 = ran clean, 2 = did not run)"
description: "`log-scan`'s `exit=` redefined as did-it-RUN (0 = printed rows, 1 = ran clean, 2 = did not run), `scan=prohibition` added, and `/code` step 2 now runs and logs a plan's prohibition criteria."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["script/log-scan", "skill/code"]
evidence: ["schema misfit"]
watches: []
---

## Change

`log-scan`'s `exit=` redefined as did-it-RUN (0 = printed rows, 1 = ran clean, 2 = did not run), `scan=prohibition` added, and `/code` step 2 now runs and logs a plan's prohibition criteria

## Evidence

schema misfit

## Result

The field conflated "ran" with "passed", which is unloggable for any grep-family scan — grep exits 1 on a clean tree. A pass was written as an error row, silently deleting the precision denominator. Both 0 and 1 now require counts

## Watch

—

## Back-out

—
