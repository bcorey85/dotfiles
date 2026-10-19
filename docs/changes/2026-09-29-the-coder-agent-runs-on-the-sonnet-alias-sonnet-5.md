---
type: "Change"
title: "The coder agent runs on the `sonnet` alias (Sonnet 5.5) in place of Opus, for every dispatch"
description: "The coder agent runs on the `sonnet` alias (Sonnet 5.5) in place of Opus, for every dispatch."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 3
components: ["agent/coder"]
evidence: ["model round"]
watches: ["coder-on-sonnet-alias"]
---

## Change

The coder agent runs on the `sonnet` alias (Sonnet 5.5) in place of Opus, for every dispatch. The prompt text does not change

## Evidence

model round

## Result

Under the Write-and-Edit rule, the same 5 tasks went from 5 of 10 runs with no code to 0 of 20, and 0 of 48 on each model in the full round. Behind the Opus code reviewer, hidden-test defects that reach the branch fell from 0.19 to 0.10 per run. Before review, Sonnet fails more (0.27 against 0.23). Review items that match no failure: 1.88 against 1.71 per review. Coder per run: wall median 38.5 s against 98.5 s. Sums over 48 runs: cache read 3.96M against 8.65M, output 351k against 602k, cache write 1.10M against 1.37M. The review cost per tree did not rise. Plan-level failures escaped review on both models. Work-log check: compare escape rates before and after the switch in the next census.

## Watch

—

## Back-out

—
