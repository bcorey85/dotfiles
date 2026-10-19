---
type: "Change"
title: "New agents `plan-fanout` (Opus, pinned) and `plan-coder-view` (Sonnet"
description: "New agents `plan-fanout` (Opus, pinned) and `plan-coder-view` (Sonnet, pinned): a plan review that sends one Sonnet agent per phase, each reading its phase as the coder who builds it next, then has Opus verify, dedupe and merge their issues."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 9
components: ["agent/plan-fanout", "agent/plan-coder-view"]
evidence: ["judgment", "replacement bench"]
watches: []
---

## Change

New agents `plan-fanout` (Opus, pinned) and `plan-coder-view` (Sonnet, pinned): a plan review that sends one Sonnet agent per phase, each reading its phase as the coder who builds it next, then has Opus verify, dedupe and merge their issues. Not wired into any skill; bench only

## Evidence

judgment, replacement bench

## Result

Three runs per arm on a planted 15-phase plan. Recall matched the live sharded review (median 10 of 12). Opus cache read fell 71%, but this pair adds 0.94M Sonnet cache write and 4.65M Sonnet cache read per review. At list price it costs 33% more than the live review. It lost to the three-phase-window pair, which costs less at one plant lower. Removed: both agent files deleted.

## Watch

—

## Back-out

restore both files from git
