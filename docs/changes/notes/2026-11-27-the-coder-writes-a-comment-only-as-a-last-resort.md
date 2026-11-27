---
type: "Change"
change_type: "changed"
title: "The coder writes a comment only as a last resort"
description: "coder-core gains one comment rule: a comment is a last resort, written only for what a busy engineer new to the code must know, and architecture goes in the repo's architecture docs; code-vocabulary's old comment guidance becomes a pointer to it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T12:11:48-06:00"}
seq: 1
kind: "user-rule"
components: ["skill/coder-core"]
evidence: ["user request", "rule meter"]
watches: []
test: ""
asked: "2026-11-27: asked by the user"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `coder-core`, `Readability comes first`: a new bullet says comments are a last resort, written only for what a busy engineer new to the code must know, with architecture kept in the repo's architecture docs.
- `_shared/code-vocabulary.md`: the section that told the coder what a comment may say is replaced by a pointer to coder-core. The rule lives where every coder loads it.

## Evidence

user request: the user wants fewer comments in every repo, and asked for one comment rule, reworded, in place of the old guidance.

Rule meter CC01 (Sonnet coder writes a late-fee policy function with a test; no comment gate in either arm; two runs per cell). Added comment lines that are no keep kind / longest such block, run 1 then run 2:

| framing | rule on | rule off |
|---|---|---|
| supportive | 0/0, 1/1 | 2/1, 2/1 |
| neutral | 3/1, 2/1 | 2/1, 2/1 |
| competing | 10/1, 10/1 | 10/1, 14/2 |
| total unkept lines | 26 | 32 |

Compliance (at most 3 unkept lines, no block over 2): on 4 of 6, off 4 of 6. The rule cuts the unkept lines from 32 to 26 but changes no verdict; under a task that asks for a comment on each branch, the coder writes them in both arms. The comment gate holds the line in a live session.

## Result

—

## Watch

—

## Back-out

Delete the bullet from `coder-core/SKILL.md` and restore the code-vocabulary section from the commit before this change.
