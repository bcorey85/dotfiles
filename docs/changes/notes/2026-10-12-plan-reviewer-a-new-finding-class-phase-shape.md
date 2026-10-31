---
type: "Change"
change_type: "changed"
title: "plan-reviewer now flags oversized phases, a skeleton phase with no Phase 0 contract, and criteria files over 8 criteria"
description: "plan-reviewer has a new finding class, phase shape: it flags a phase past about 10 files with no atomic reason, a skeleton phase that never runs a Phase 0 contract, and an acceptance-criteria file with more than 8 criteria."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["agent/plan-reviewer"]
evidence: ["seeded round", "census"]
watches: ["plan-review-phase-shape"]
proof: ["2026-10-09-planfmt-sealed-planfmt-md-graded-edit"]
impact: {"metric": "quality", "before": 9, "after": 0, "unit": "planted shape defects missed (of 9)", "finding": "2026-10-09-planfmt-sealed-planfmt-md-graded-edit", "better": "lower"}
---

## Change

plan-reviewer has a new finding class, phase shape. It flags a phase past about 10 files with no atomic reason, a skeleton phase that never runs a Phase 0 contract, and an acceptance-criteria file with more than 8 criteria. The opencode copy matches

## Evidence

seeded round, census

## Result

Seeded plan: the reviewer caught 0 of 3 planted shape defects before and 3 of 3 after, in 3 of 3 runs. Old plants 23 against 24 of 24. False shape alarms on a clean plan: 0 in 3. Cache read per arm type about level. At work, 76 of 176 plan defects got past plan review.

## Watch

plan-drift escapes past plan review, and whether the criteria cap fires on most plans.

## Back-out

delete the paragraph
