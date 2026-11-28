---
type: "QueueItem"
title: "retire branch-recap or mark it legacy against close-branch"
description: "Removes the second recap template that overlaps close-branch, up to about 100 lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:42:06-06:00"}
kind: "method"
status: "running"
rank: 1023
blocked_by: []
source: "claude/.claude/skills/branch-recap/SKILL.md"
components: ["skill/branch-recap", "skill/test-audit", "skill/close-branch"]
not_dup: "The 2026-11-04 change merged four closing phases into one close pass, but branch-recap and test-audit still call themselves the fourth and third closing phase."
---

## Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

- branch-recap and test-audit still call themselves the "fourth" and "third" closing phase; _shared/closing-phases.md says close-branch is the single closing phase.
- close-branch Step 6 and branch-recap:58-91 carry two overlapping recap templates.
- close-branch's description lists its steps (check 1).

## Done when

The user picks retire or legacy; no skill names a closing phase other than close-branch; one recap template remains; `bash tests/run.sh` passes.
