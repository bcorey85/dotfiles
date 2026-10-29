---
type: "Change"
change_type: "changed"
title: "Review asks carry the finding id the logger printed"
description: "Each ask in the review-loop packet carries the `finding_id` that log-review-finding printed, the ask outcome supersedes the ask row by that id, and `desc=` is no longer stored."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T05:06:55-05:00"}
seq: 4
kind: "behavior"
components: ["agent/review-loop", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: ""
unmeasured: "No work-log field counts ask outcome rows that found their ask row against the ones that did not."
---

## Change

The ledger writer switch commit changed these prompt blocks, with no change file. This file records them after the fact.

- `agents/review-loop.md`, `## Return packet`: each `ask:` item adds `finding_id`, the id that log-review-finding printed for that ask row.
- `skills/review/SKILL.md` and `skills/fix/SKILL.md`, `present-asks`: each outcome row carries the ask's `finding_id`, and the note is not stored. An ask with no `finding_id` logs nothing.
- `skills/_shared/finding-log.md`, `## Emit`: `phase=` is left out when there is no phase, and the finding call drops `desc=` and prints `finding_id=<id>`.
- `skills/_shared/finding-log.md`, `## Rules that make the data usable`: an unknown class stores as `other`. `desc=` is accepted and never stored. The ask outcome supersedes the ask row by its id.

## Evidence

Judgment: the ledger keeps no free text, and an ask outcome needs a key to find its ask row. A missing or bad id only skips the log row. It never stops the review: the two follow-up fixes that skip a placeholder id show this.

## Result

Ask outcomes join to their ask rows by id. A review with no ledger runs as before and logs less.

## Watch

None. See `unmeasured`.

## Back-out

Restore the five blocks from the dotfiles history before the ledger writer switch commit.
