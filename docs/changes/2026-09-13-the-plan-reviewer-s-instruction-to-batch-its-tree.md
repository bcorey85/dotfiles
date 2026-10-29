---
type: "Change"
change_type: "removed"
title: "The plan reviewer's instruction to batch its tree checks was removed"
description: "The plan reviewer's instruction to batch its tree checks was removed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-13T00:00:00-05:00"}
seq: 1
kind: "behavior"
reverts: "2026-09-12-the-plan-reviewer-now-batches-its-tree-checks-it"
impact: {"metric": "tokens", "before": 1300000, "after": 800000, "unit": "tokens", "finding": "2026-09-12-tokbatch-1"}
components: ["agent/plan-reviewer"]
evidence: ["controlled replay"]
watches: []
---

## Change

The plan reviewer's instruction to batch its tree checks was removed.

## Evidence

controlled replay

## Result

The instruction did not make the reviewer batch: its commands per turn barely moved and no turn issued more than three. Tokens per run fell by about two fifths because it ran over a third fewer checks. A later blind grading of the same reports found what it caught equal within noise to the unchanged prompt, so the removal rests only on the rule not doing what it says, and it may return under a new test.

## Watch

—

## Back-out

—
