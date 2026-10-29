---
type: "Change"
change_type: "changed"
title: "The plan reviewer's instruction to batch its tree checks is back"
description: "The plan reviewer's instruction to batch its tree checks is back."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-13T00:00:00-05:00"}
seq: 2
kind: "behavior"
reverts: "2026-09-13-the-plan-reviewer-s-instruction-to-batch-its-tree"
components: ["agent/plan-reviewer"]
evidence: ["seeded round"]
watches: []
---

## Change

The plan reviewer's instruction to batch its tree checks is back.

## Evidence

seeded round

## Result

Against a plan seeded with ten known defects, the batched reviewer found eight of them per run against nearly nine for the unchanged prompt, a difference inside the test's noise, while spending about two fifths fewer tokens per run, nearly all of it cache reads and turns; the defects it missed most were the same three the unchanged prompt missed most. A second reviewer launched beside the first was tested in the same round and found no more than one reviewer does at a quarter more tokens, so the review stays a single reviewer.

## Watch

—

## Back-out

—
