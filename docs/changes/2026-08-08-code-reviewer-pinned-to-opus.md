---
type: "Change"
change_type: "changed"
title: "`code-reviewer` now runs on opus and catches defects sonnet missed"
description: "`code-reviewer` is fixed to opus, which caught planted defects that sonnet missed with the same prompt, at a higher price per review."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["seeded round"]
watches: []
---

## Change

`code-reviewer` now always runs on opus. Sonnet at this gate missed planted defects the same prompt caught on opus; the price of every review rises.

## Evidence

seeded round

## Result

Sonnet at this gate missed planted defects the same prompt caught on opus. Raises the price of every review — the most expensive single change in this table

## Watch

—

## Back-out

—
