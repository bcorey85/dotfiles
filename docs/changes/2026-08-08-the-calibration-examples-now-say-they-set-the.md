---
type: "Change"
title: "The calibration examples now say they set the height of the bar rather than its subject"
description: "The calibration examples now say they set the height of the bar rather than its subject."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 16
components: ["shared/reviewer-calibration"]
evidence: ["census"]
watches: []
---

## Change

The calibration examples now say they set the height of the bar rather than its subject

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/reviewer-calibration.md`, section `## Calibration Anchor` (evidence: census):

The merge-blocking question and the examples that set the bar's height. Adopted by the four specialist reviewers, untested there. The diff reviewer no longer loads it: two replicates at opus found it inert on recall and on false findings for that reviewer.

## Result

Every example is a general code-correctness one, but four of the five reviewers that adopt the section review something else, and one had already grown its own restated copy to work around the mismatch

## Watch

—

## Back-out

—
