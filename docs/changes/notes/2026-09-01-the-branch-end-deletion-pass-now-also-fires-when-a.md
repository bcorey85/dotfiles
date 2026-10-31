---
type: "Change"
change_type: "changed"
title: "The branch-end deletion pass now also fires when a branch's total added lines clear a threshold"
description: "The branch-end deletion pass now also fires when a branch's total added lines clear a threshold, not only when one module does."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["skill/branch-recap"]
evidence: ["judgment"]
watches: []
---

## Change

The branch-end deletion pass now also fires when a branch's total added lines clear a threshold, not only when one module does

## Evidence

judgment

## Result

The gate fired on a per-module maximum alone, so a branch could carry hundreds of deletable lines spread across five modules with no single module clearing the floor, and the pass could not run at all. Unnecessary code spreads along with its consumers — a producer and the state field, routing branch, and prompt clause that serve only it land in different modules, each plausible to its own caller — so a per-module maximum is blind to exactly the shape that is most thoroughly integrated. Still one module per branch, still opt-in per finding; the threshold is a chosen anchor, not a derived one.

## Watch

—

## Back-out

—
