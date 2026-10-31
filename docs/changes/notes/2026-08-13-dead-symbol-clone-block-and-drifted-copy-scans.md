---
type: "Change"
change_type: "removed"
title: "The branch recap no longer runs the dead-symbol, clone-block and drifted-copy scans"
description: "The branch recap drops three scans that produced 513 candidates across 6 runs and none confirmed; the prohibition scans stay."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-13T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["script/log-scan"]
evidence: ["removal round"]
watches: []
---

## Change

The branch recap no longer runs the dead-symbol, clone-block and drifted-copy scans. Their firing site, the three scan scripts and their `log-scan` validator entries are all removed.

## Evidence

removal round

## Result

513 candidates across 6 runs (0 confirmed), and 0 recall signal — no escape ever logged as one these scans covered and missed. Added on an a-priori structural argument, never a measured catch. clone-block/drifted-copy are fixture-parallelism noise by construction; dead-symbol's only unique-over-a-linter niche (TEST-ONLY symbols) confirmed 0/28, so it is either redundant with `knip`/`deadcode` or unproven. branch-recap Step 2, the three scan scripts, and their `log-scan` validator names all removed. Prohibition scans retained.

## Watch

—

## Back-out

—
