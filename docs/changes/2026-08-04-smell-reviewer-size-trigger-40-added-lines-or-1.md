---
type: "Change"
change_type: "changed"
title: "`smell-reviewer` runs on changes of 40 or more added lines or one new source file"
description: "`smell-reviewer` runs when a change adds at least 40 lines or at least one new source file; the 98%/91% action rates show the trigger is calibrated."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/smell-reviewer"]
evidence: ["gate ranking"]
watches: []
---

## Change

`smell-reviewer` runs when a change adds at least 40 lines or at least one new source file. Kept: 98%/91% action rates show the trigger is calibrated.

## Evidence

gate ranking

## Result

Kept. 98%/91% action rates say it's calibrated

## Watch

—

## Back-out

—
