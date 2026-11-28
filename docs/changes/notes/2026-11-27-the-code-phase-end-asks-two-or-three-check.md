---
type: "Change"
change_type: "added"
title: "The code phase end asks two or three check-yourself questions with file lines"
description: "A /code phase stop block now carries two or three check-yourself questions about the phase's code, each ending on the path:line that answers it, written from the coder's WHY notes and the diff. No new agent and no change to the coder report."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T19:01:58-06:00"}
seq: 6
kind: "structured"
components: ["skill/code"]
evidence: ["rule meter", "tests"]
watches: []
test: ""
asked: ""
proof: ["2026-11-27-the-code-phase-end-block-s-check-yourself-lines"]
unmeasured: "No intake metric reads whether a user answers the questions or catches a misread phase with them; the final keep or drop is the user's try on one real branch."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`skills/code/phase-end-block.md` block B gains a `Check yourself` list after the behavior delta: each line is a
question about the phase's code that ends on a `path:line`. The fork writes two or three from the coder's `WHY:` notes
and the phase's diff. Each asks what calls a new function, what happens when a new branch fails, or what state a new
write changes, and the block never answers them.

## Evidence

Rule meter scenario PQ01 in agent-evals: a two-phase void-invoice plan with Phase 1 ticked, a coder report with
BEHAVIOR and WHY lines, and the phase's two new files uncommitted. The off arm is the same block file with the
check-yourself lines and their writing sentence removed. Opus, the fork told to print the phase-complete block.

## Result

Neutral level, 8 runs per arm: on 8/8 printed two or more question lines ending on a changed file's `path:line`, off
0/8 (Wilson 95% [0.68, 1.00] vs [0.00, 0.32]). Supportive and competing, 1 run per arm: on 1/1 each, off 0/1 each.
Every off run printed the phase header with no question line.

## Watch

None. Whether the questions help is the user's call after one real branch.

## Back-out

Revert the two block-B edits in `skills/code/phase-end-block.md` and restore its rule-anchors row hash to 8b58aeed.
