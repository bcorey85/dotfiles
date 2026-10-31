---
type: "Change"
change_type: "changed"
title: "The branch-exit skill now states each of its own rules once"
description: "The branch-exit skill states each of its own rules once: never-commit lives in the output contract, never-re-run-a-gate in the opening, and the other copies point at them."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 26
kind: "behavior"
components: ["skill/branch-recap"]
evidence: ["census"]
watches: []
---

## Change

The branch-exit skill states each of its own rules once: never-commit lives in the output contract, never-re-run-a-gate in the opening, and the other copies point at them

## Evidence

census

## Result

Three copies of never-commit and two of never-re-run-a-gate in one file, none drifted yet. Nothing reads the removed text, and the class where copies drift apart is the one that reliably produces a rule that fires wider than the one that was reasoned about

## Watch

—

## Back-out

—
