---
type: "Change"
change_type: "changed"
title: "Coder updates the docs a fix makes stale"
description: "The coder now updates the comments, docs and messages a fix makes wrong in 62% of runs, up from 0% (0/16 → 10/16). Coder-core gains one sentence under Fixing a review finding."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T11:18:37-06:00"}
seq: 6
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: ["coder-updates-stale-docs"]
test: ""
asked: ""
proof: ["2026-11-02-stale-docs-rule-makes-the-coder-update-the-docs-a"]
impact: {"metric": "quality", "before": 100, "after": 38, "unit": "% of runs leaving stale text", "finding": "2026-11-02-stale-docs-rule-makes-the-coder-update-the-docs-a", "better": "lower"}
unmeasured: ""
overlap: "Three open watches read docs findings per review run. This one ships anyway: its proof is a 16-run bench with non-overlapping intervals, and a docs-findings drop after 2026-11-02 is credited jointly, not to this edit alone."
---

## Change

`coder-core` `## Fixing a review finding` gains: update every comment, docstring, doc file and user-facing message that
describes the old behavior, in the same change; search for the old wording and the old value, and name each place.

## Evidence

Rule-meter runs on one fixture, 16 per arm, with behavior checks hidden from the coder.

## Result

Runs that left no stale text went from 0 of 16 to 10 of 16. Every rule-on miss left only the README.

## Watch

`coder-updates-stale-docs`: docs-class review findings per review run, expected down.

## Back-out

Delete the stale-docs sentence from `## Fixing a review finding` in `claude/.claude/skills/coder-core/SKILL.md`.
