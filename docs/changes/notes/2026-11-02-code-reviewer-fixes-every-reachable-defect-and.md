---
type: "Change"
change_type: "changed"
title: "Code reviewer fixes every reachable defect and sweeps sibling sites"
description: "One review pass now names 14 of 19 known bugs as fixes, up from 8 (blind). A reachable defect is always a fix, and a found defect sends the reviewer to every other site of its kind. Each pass costs 9% more tokens and gives the coder about 75% more items."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T00:11:20-06:00"}
seq: 1
kind: "structured"
components: ["agent/code-reviewer"]
evidence: ["replay bench"]
watches: ["reviewer-reachable-sweep-escapes"]
test: ""
asked: ""
proof: ["2026-11-02-two-code-reviewer-rules-double-the-known-bugs-one"]
impact: {"metric": "quality", "before": 8, "after": 14, "unit": "of 19 known bugs named as fixes", "finding": "2026-11-02-two-code-reviewer-rules-double-the-known-bugs-one", "better": "higher"}
unmeasured: ""
overlap: "The branch-exit-peer-review-escapes watch reads the same escapes metric from 2026-11-01, so its reading and this one cannot be split."
---

## Change

`code-reviewer` gains two rules. Under `### Nit`: a defect a user or caller can reach is a `fix`, however rare the path,
and a nit never describes wrong behavior. At the end of Step 2: when you find a defect, search the whole diff for every
other site of the same kind, and report each site.

## Evidence

A blind replay on sealed phases of three tickets.

## Result

Known bugs named as fixes went from 8 of 19 to 14 of 19, and none was lost. Reachable defects named went from 13 to 34.
Fix items rose about 75%, and tokens rose 9%.

## Watch

`reviewer-reachable-sweep-escapes`: escapes per review run fall.

## Back-out

Delete both rules from `claude/.claude/agents/code-reviewer.md`.
