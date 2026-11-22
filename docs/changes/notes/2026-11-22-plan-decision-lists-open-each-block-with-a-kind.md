---
type: "Change"
change_type: "changed"
title: "Plan decision lists open each block with a kind emoji"
description: "The eng-spec recommendation list marks each decision block with 🔷 and each open question with ❓, puts ➡ before the recommendation and a rule line between blocks, so the user can tell the blocks apart at a glance."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T09:57:26-06:00"}
seq: 1
kind: "user-rule"
components: ["skill/eng-spec"]
evidence: ["user request", "rule meter"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: ["2026-11-22-emoji-headings-on-plan-decision-blocks-the-rule"]
unmeasured: "No intake number reads how fast the user scans a decision list. The meter graded the heading emoji only: the ➡ before the recommendation, the rule line between blocks and the drill-down heading have no run. The stack does not apply: the rule formats a chat message."
---

## Change

`skills/eng-spec/phases/5-decisions.md`, in the recommendation-list step: one new bullet. Each block's heading starts
with an emoji for its kind (🔷 decision, ❓ open question), ➡ goes before `Rec:`, a `---` line goes between blocks, a
⚠ goes after the kind emoji, and a drill-down section opens with the same emoji heading. The example block above the
bullet is unchanged.

## Evidence

user request: the user finds the plain `D1`, `Q1` labels hard to track by eye and asked for emoji to break up the
sections. rule meter: the bullet, placed in this file, was run with and without its text.

## Result

Opus, the phase file as it ships, 8 runs per cell, two decision queues. Replies whose every decision and question
heading carried its emoji: first queue, neutral 8/8 with the bullet and 0/8 without, competing 8/8 and 0/8; second
queue, neutral 8/8 and 0/8. See `unmeasured` for the parts of the bullet no run graded.

## Watch

None: see `unmeasured`.

## Back-out

Delete the bullet from `skills/eng-spec/phases/5-decisions.md`.
