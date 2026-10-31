---
type: "Change"
change_type: "added"
title: "New planning-lane logger writes one row per finalized or abandoned plan"
description: "New planning-lane logger writing one row per finalized or abandoned plan (phases, criteria, decisions, research questions, self-caught gaps, falsified claims), wired into the spec finalization phase, with an audit step that reports plan defects per plan and per criterion."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 18
kind: "behavior"
components: ["script/log-spec-run"]
evidence: ["census"]
watches: []
---

## Change

New planning-lane logger writing one row per finalized or abandoned plan (phases, criteria, decisions, research questions, self-caught gaps, falsified claims), wired into the spec finalization phase, with an audit step that reports plan defects per plan and per criterion

## Evidence

census

### Anchor reasons

Anchor `skills/architect-core/SKILL.md`, section `## Two-Stage Dispatches` (evidence: census):

The exploration brief and the full plan as two dispatches, research documents as ground truth, and the DESIGN GAPS rule for new decisions in the second stage. The spec skill's explore and finalize phases drive the two stages. Its finalize and review phases and the criteria lint script read the DESIGN GAPS marker. Kept in both texts of the removal round, and every plan held one DESIGN GAPS section.

## Result

Planning was the only stage logging nothing, so its defect count rose and fell with planning volume and carried no information either way. The last time a rate was needed, the denominator had to be reconstructed from planning directories that survive in git history only because they are committed before being retired. Abandoned plans are logged too — planning that produced no code was still paid for.

## Watch

—

## Back-out

—
