---
type: "Change"
change_type: "changed"
title: "Telemetry rows now record the repo rather than the checkout"
description: "Telemetry rows now record the repo rather than the checkout, the finding-class vocabulary is validated and gains a `docs` value, and a gate's verdict is spelling-normalized instead of refused."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-07T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["script/log-review-finding", "script/log-escape"]
evidence: ["log census"]
watches: []
---

## Change

Telemetry rows now record the repo rather than the checkout, the finding-class vocabulary is validated and gains a `docs` value, and a gate's verdict is spelling-normalized instead of refused

## Evidence

log census

## Result

Three defects that made the per-gate log unusable for the questions it exists to answer. A worktree checkout logged as its own repo, so one repo's rates split across every branch it had ever been worked on. Nearly half of all findings carried the catch-all class, and the largest group inside it was prose that was wrong about correct code — a class the vocabulary had no name for. And the verdict field accepted only three spellings, so gates with no natural pass/fail vocabulary had their whole row refused and lost their denominator; the synonyms they actually reach for are now folded in and only an unmappable value is rejected.

## Watch

—

## Back-out

—
