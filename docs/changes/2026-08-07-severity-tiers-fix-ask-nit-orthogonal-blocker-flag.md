---
type: "Change"
change_type: "changed"
title: "Review findings are now labelled `fix`, `ask` or `nit`, with a separate `blocker` flag"
description: "Each review finding says what to do with it (`fix`, `ask` or `nit`) and carries a `blocker` flag, in place of a severity tier."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-07T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["skill/fix"]
evidence: ["629-run log"]
watches: []
---

## Change

Review findings are now labelled `fix`, `ask` or `nit`, with an independent `blocker` flag. Before, they carried a severity tier.

## Evidence

629-run log

## Result

`fixed` (331) > `critical+high` (138) — the tier predicted nothing the loop acted on. Matches Google eng-practices and Conventional Comments

## Watch

—

## Back-out

—
