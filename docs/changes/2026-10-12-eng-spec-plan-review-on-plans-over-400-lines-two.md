---
type: "Change"
title: "`/eng-spec` plan review on plans over 400 lines: two Opus shards instead of three"
description: "`/eng-spec` plan review on plans over 400 lines: two Opus shards instead of three."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 13
components: ["skill/eng-spec"]
evidence: ["removal round"]
watches: ["plan-review-two-shards"]
---

## Change

`/eng-spec` plan review on plans over 400 lines: two Opus shards instead of three. The shard that read only file lines and verification headings is dropped

## Evidence

removal round

## Result

Six runs per arm on a planted 15-phase plan. Recall median 10 of 12 both ways (two shards 10–11, three 9–10). The test that cannot fail was caught 6 of 6 against 5 of 6. The dropped shard caught nothing the first-half shard missed in any run. Per review: Opus cache write 192k against 271k, cache read 4.70M against 5.72M, list price $3.61 against $4.68 (−23%). Wall clock level, 246 s against 243 s.

## Watch

plan-review escapes per spec run in the work logs.

## Back-out

restore the seam bullet, its lossy-view paragraph and "three" in the review phase file
