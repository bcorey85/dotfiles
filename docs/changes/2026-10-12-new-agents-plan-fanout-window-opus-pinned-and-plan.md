---
type: "Change"
change_type: "added"
title: "New agents `plan-fanout-window` (Opus, pinned) and `plan-window-view` (Sonnet"
description: "New agents `plan-fanout-window` (Opus, pinned) and `plan-window-view` (Sonnet, pinned): the same fan-out plan review, but each Sonnet agent reads a three-phase window (overlapping by one phase) and never the full plan, 7 agents instead of 15."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 10
kind: "behavior"
components: ["agent/plan-fanout-window", "agent/plan-window-view"]
evidence: ["judgment", "token breakdown", "replacement bench"]
watches: []
---

## Change

New agents `plan-fanout-window` (Opus, pinned) and `plan-window-view` (Sonnet, pinned): the same fan-out plan review, but each Sonnet agent reads a three-phase window (overlapping by one phase) and never the full plan, 7 agents instead of 15. Not wired into any skill; bench only

## Evidence

judgment, token breakdown, replacement bench

## Result

Three runs per arm on a planted 15-phase plan. Recall median 9 of 12 against the live sharded review's 10; it never caught a test guard that cannot fail. Opus cache read fell 86% (0.94M against 6.84M) and wall time 24%, while the pair adds 0.38M Sonnet cache write and 2.95M Sonnet cache read. About 34% cheaper per review than the live review at list price. It won the bench's decision table. Now wired in: `/eng-spec` round 1 on plans over 400 lines runs `scripts/plan-windows` and dispatches `plan-fanout-window` in place of the three Opus shards. Plans at or under 400 lines and DEEP round 2 still use `plan-reviewer`. Watch the work-log plan-review escape rate per spec run, and revert if it rises.

## Watch

—

## Back-out

restore the shard text in the review phase file and delete both agent files and the script
