---
type: "Change"
change_type: "added"
title: "A new check verifies that every calibration section a reviewer names actually exists"
description: "A new check verifies that every calibration section a reviewer names actually exists, firing when either side is edited."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 17
kind: "behavior"
components: ["script/calibration-refs-guard", "shared/reviewer-calibration"]
evidence: ["judgment"]
watches: []
---

## Change

A new check verifies that every calibration section a reviewer names actually exists, firing when either side is edited

## Evidence

judgment

## Result

The prose warning it replaces failed once already, silently, and the failure mode is invisible: an agent pointed at a missing heading still produces a plausible review. Reports rather than blocks, because renaming a section is legitimate work and only the unfinished half is the problem

## Watch

—

## Back-out

—
