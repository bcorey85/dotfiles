---
type: "Change"
change_type: "changed"
title: "Coder decides each control's state during an async action"
description: "The coder now handles every control during an async action in 88-100% of runs, up from 0% (0/8 → 7/8 on a dialog, 0/8 → 8/8 on a search panel). Coder-core gains one paragraph on what controls do mid-request and on close."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T00:11:20-06:00"}
seq: 1
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-01-async-view-rule-leaves-every-control-safe-in-88-of"]
impact: {"metric": "quality", "before": 100, "after": 12, "unit": "% of runs with an unsafe control", "finding": "2026-11-01-async-view-rule-leaves-every-control-safe-in-88-of", "better": "lower"}
unmeasured: "Finding text in the work logs is hashed, so no intake number can tell an in-flight bug from any other bug."
---

## Change

`coder-core` gains `## Async actions in a view`: for each async action added to a view, decide what every control does
while it runs and what happens if the view closes, clear view state on close, and test one control used mid-request and
one close-and-reopen.

## Evidence

Rule-meter runs on two fixtures, 8 per arm, with behavior checks hidden from the coder. In-flight and stale-state bugs
appear on two of three labeled bench tickets.

## Result

Safe runs went from 0 of 8 to 7 of 8 on a dialog, and from 0 of 8 to 8 of 8 on a search panel.

## Watch

None: see `unmeasured`.

## Back-out

Delete the `## Async actions in a view` section from `claude/.claude/skills/coder-core/SKILL.md`.
