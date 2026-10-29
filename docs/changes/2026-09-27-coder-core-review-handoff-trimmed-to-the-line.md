---
type: "Change"
change_type: "changed"
title: "coder-core review handoff trimmed to the line formats; the calibration clauses on BEHAVIOR, WHY"
description: "coder-core review handoff trimmed to the line formats; the calibration clauses on BEHAVIOR, WHY, REFACTOR CANDIDATES, REVIEW and PLAN-IMPACT: yes removed, \"one line per note\" kept."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 16
kind: "behavior"
components: ["skill/coder-core"]
evidence: ["removal round"]
watches: []
---

## Change

coder-core review handoff trimmed to the line formats; the calibration clauses on BEHAVIOR, WHY, REFACTOR CANDIDATES, REVIEW and PLAN-IMPACT: yes removed, "one line per note" kept

## Evidence

removal round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Review handoff (last lines of your report)` (evidence: removal round):

The BEHAVIOR, WHY, REFACTOR CANDIDATES, REVIEW, and PLAN-IMPACT: yes lines the review loop parses. Trimmed to the format only; routing and plan-impact reporting held on all tasks. "One line per note" stays: without it, one WHY line joined two ranges with a comma.

## Result

Routing and plan-impact reporting held on all three tasks under both wordings. Without "one line per note", one WHY line joined two ranges with a comma, so those words stay. About 75 tokens per coder request, about 1.0M a week.

## Watch

—

## Back-out

—
