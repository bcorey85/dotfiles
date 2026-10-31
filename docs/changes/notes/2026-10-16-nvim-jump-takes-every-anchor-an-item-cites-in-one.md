---
type: "Change"
change_type: "changed"
title: "`nvim-jump` takes every anchor an item cites in one call, each with a one-line `--note`"
description: "`nvim-jump` takes every anchor an item cites in one call, each with a one-line `--note`, and `]k`/`[k` step through them in nvim."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-16T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["shared/nvim-jump", "skill/stage", "skill/verify", "skill/review", "skill/fix", "skill/code", "skill/branch-recap"]
evidence: ["judgment"]
watches: []
---

## Change

`nvim-jump` takes every anchor an item cites in one call, each with a one-line `--note`, and `]k`/`[k` step through them in nvim. A set shown together is one call in shown order. New jump points: the `/stage` read queue (`stage.mjs` now gives each entry its first changed line), the `/verify` evidence table and its covering tests, and the `ask[]` list in `/review`, `/fix` and `/code`. The per-entry jumps in `/branch-recap` and in the `/code` queue step are deleted, because `/stage` now jumps the queue

## Evidence

judgment

## Result

Effect unmeasured.

## Watch

—

## Back-out

restore the one-anchor rules in `_shared/nvim-jump.md`, delete the new jump lines, and restore the two deleted ones
