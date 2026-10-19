---
type: "Change"
title: "`/eng-spec` plan review back to the three Opus shards on plans over 400 lines"
description: "`/eng-spec` plan review back to the three Opus shards on plans over 400 lines."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 12
components: ["skill/eng-spec"]
evidence: ["replacement bench"]
watches: []
---

## Change

`/eng-spec` plan review back to the three Opus shards on plans over 400 lines. `plan-fanout-window`, `plan-window-view` and `scripts/plan-windows` deleted

## Evidence

replacement bench

## Result

Six runs per arm on a planted 15-phase plan. The window review never caught a test that cannot fail on the defect it names: 0 of 6, against 5 of 6 for the shards. Recall median 9 of 12 against 10. Its saving was about 25% at list price ($3.40 against $4.56 per review), and it needs 8 agent slots at once, so a busy session serialized it.

## Watch

—

## Back-out

restore the three files from git and the window text in the review phase file
