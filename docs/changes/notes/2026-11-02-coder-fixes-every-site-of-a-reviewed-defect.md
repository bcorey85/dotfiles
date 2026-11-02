---
type: "Change"
change_type: "changed"
title: "Coder fixes every site of a reviewed defect"
description: "The coder now fixes every sibling site of a reviewed defect in 94% of runs, up from 0% (0/16 → 15/16, two fixtures). Coder-core gains one sentence: when fixing a review finding, find and fix every other site with the same defect."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T07:48:12-06:00"}
seq: 3
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-02-fix-sweep-rule-makes-the-coder-fix-every-site-of-a"]
impact: {"metric": "quality", "before": 100, "after": 6, "unit": "% of runs leaving a sibling site unfixed", "finding": "2026-11-02-fix-sweep-rule-makes-the-coder-fix-every-site-of-a", "better": "lower"}
unmeasured: "Finding text in the work logs is hashed, so no intake number can tell an unswept sibling from any other round-two finding."
---

## Change

`coder-core` gains `## Fixing a review finding`: search the code for every other site with the same defect, fix those
too, and name each site in the report.

## Evidence

Rule-meter runs on two fixtures with different defect classes, 8 per arm each, with behavior checks hidden from the
coder.

## Result

Runs that fixed every site went from 0 of 16 to 15 of 16.

## Watch

None: see `unmeasured`.

## Back-out

Delete the `## Fixing a review finding` section from `claude/.claude/skills/coder-core/SKILL.md`.
