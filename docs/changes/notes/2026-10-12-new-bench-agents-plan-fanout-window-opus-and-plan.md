---
type: "Change"
change_type: "added"
title: "New bench agents `plan-fanout-window-opus` and `plan-window-view-opus`"
description: "New bench agents `plan-fanout-window-opus` and `plan-window-view-opus`: the three-phase-window plan review with Opus as the window reviewers instead of Sonnet."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 11
kind: "behavior"
components: ["agent/plan-fanout-window-opus", "agent/plan-window-view-opus"]
evidence: ["judgment", "model swap bench"]
watches: []
---

## Change

New bench agents `plan-fanout-window-opus` and `plan-window-view-opus`: the three-phase-window plan review with Opus as the window reviewers instead of Sonnet. Not wired into any skill; bench only

## Evidence

judgment, model swap bench

## Result

One run on the planted 15-phase plan: 8 of 12, no better than the Sonnet windows (8–9). Cost about 1.9× the live sharded review: 0.61M Opus cache write and 11.7M Opus cache read, 314 s. Removed: both agent files deleted.

## Watch

—

## Back-out

none needed
