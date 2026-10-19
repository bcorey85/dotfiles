---
type: "Change"
title: "The calibration file's opening question now routes a borderline finding to the same place its own self-check"
description: "The calibration file's opening question now routes a borderline finding to the same place its own self-check does, and stops colliding with the reserved label."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 15
components: ["shared/reviewer-calibration"]
evidence: ["census"]
watches: []
---

## Change

The calibration file's opening question now routes a borderline finding to the same place its own self-check does, and stops colliding with the reserved label

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/reviewer-calibration.md`, section `## Disposition` (evidence: census):

One disposition per finding, the blocker flag, and the plan-impact routing. Adopted by the four specialist reviewers, untested there. The diff reviewer no longer loads it and carries the plan-impact prefix in its own report template instead.

Anchor `skills/_shared/reviewer-calibration.md`, section `## Self-Check Before Reporting` (evidence: judgment):

The calibration question run once more per finding. Adopted by the four specialist reviewers, untested there. The diff reviewer no longer loads it, for the same reason as the anchor block.

## Result

The question sent a worth-mentioning item to a section no reviewer's output format has, while the self-check called the same item the lowest disposition. It also used the word "block" in a sense opposite to the reserved stop-the-phase label defined a few lines below

## Watch

—

## Back-out

—
