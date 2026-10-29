---
type: "Change"
change_type: "changed"
title: "The code reviewer now runs its own structure pass, so the review loop skips the separate Opus structure reviewer"
description: "When the structure domain is eligible, the code reviewer runs its own structure pass and the review loop no longer dispatches the Opus structure reviewer."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["agent/review-loop", "agent/code-reviewer", "agent/smell-reviewer", "agent/test-reviewer"]
evidence: ["seeded bench"]
watches: []
---

## Change

When the structure domain is eligible, the code reviewer runs its own structure pass (`structure: on`) on the source files, so the review loop no longer dispatches the Opus structure reviewer. And the test reviewer runs beside it on the diff's test files. Diffs with no test files keep the whole list on the code reviewer

## Evidence

seeded bench

## Result

On one 814-line tree (411 test lines), 5 runs each: logic bugs 30/30 both; test gaps 15/15 vs 10/15; structure issues 28/30 vs 30/30, with 22 vs 27 filed as fix or ask; Opus median per run, cache read 148k vs 231k (−36%), cache write 46k vs 61k, output flat. Slowest reviewer median 70 s vs 75 s. Applies only to diffs that trip the structure size trigger. Check after the edit: structure findings per loop and test-gap escapes in the work logs

## Watch

—

## Back-out

—
