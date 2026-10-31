---
type: "Change"
change_type: "changed"
title: "Spec defects are now loggable and logged — `gate_missed=eng-spec`, `stage_found=phase-gate`"
description: "Spec defects are now loggable and logged — `gate_missed=eng-spec`, `stage_found=phase-gate`, and a `/code` step-3b rule filing the row when a `FAILING-TEST` resolves as a plan defect."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["skill/eng-spec", "skill/code"]
evidence: ["log gap"]
watches: []
---

## Change

Spec defects are now loggable and logged — `gate_missed=eng-spec`, `stage_found=phase-gate`, and a `/code` step-3b rule filing the row when a `FAILING-TEST` resolves as a plan defect

## Evidence

log gap

## Result

Three same-class defects in one project, **none in the escape log**: the enum had no value for "the plan was wrong", so each fell through to a prose friction file where nothing aggregates it. Also the only class structurally invisible to review — a wrong spec and a faithful diff agree with each other, so the remediation was never on any dial

## Watch

—

## Back-out

—
