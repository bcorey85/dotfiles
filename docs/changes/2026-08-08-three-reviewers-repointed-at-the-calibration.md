---
type: "Change"
change_type: "fixed"
title: "Three reviewers repointed at the calibration section they were told to adopt"
description: "Three reviewers repointed at the calibration section they were told to adopt, after it was renamed and they were not updated."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 14
kind: "fix"
components: ["agent/code-reviewer", "agent/smell-reviewer", "shared/reviewer-calibration"]
evidence: ["census"]
watches: []
---

## Change

Three reviewers repointed at the calibration section they were told to adopt, after it was renamed and they were not updated

## Evidence

census

### Anchor reasons

Anchor `skills/_shared/reviewer-calibration.md`, section `# Reviewer Calibration (single source of truth)` (evidence: census):

Names the four specialist adopters and warns that a renamed section breaks them. The warning failed once, which is why the doctor now checks the references. The diff reviewer is no longer an adopter. The count of named headings fell to four when the memory section was removed.

Anchor `agents/smell-reviewer.md`, section `## Inherit the calibration verbatim` (evidence: removal round, census):

The calibration read with its four named sections. Byte-identical in both arms, then with a fifth name for the memory section. That name left when the memory section was removed.

## Result

The shared calibration file warns that renaming a section requires updating every agent that names it; the rename happened and three of five adopters were left pointing at a heading that no longer existed. The warning sat three lines from the edit that broke it

## Watch

—

## Back-out

—
