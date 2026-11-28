---
type: "Change"
change_type: "changed"
title: "The code-reviewer cuts each added comment a new engineer would not need"
description: "code-reviewer's Dead weight item flags each comment the diff adds that a busy engineer new to the code would not need, except a public-API doc description sentence, with delete as the fix; the opencode port matches."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T12:11:48-06:00"}
seq: 2
kind: "user-rule"
components: ["agent/code-reviewer"]
evidence: ["user request", "rule meter"]
watches: []
test: ""
asked: "2026-11-27: asked by the user"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `agents/code-reviewer.md`, Step 3 Dead weight: flag each added comment a busy engineer new to the code would not need, never a public-API doc description sentence; the fix is to delete it. The older "restates the code or narrates its history" wording is gone.
- `opencode/.config/opencode/agents/code-reviewer.md`: the comment-noise and density bullets use the same test.

## Evidence

user request: short comments pass the gate now, so the reviewer is the check that cuts the ones nobody needs.

Rule meter SR01 (Opus code-reviewer reviews a commit that adds three short comments no reader needs and one rounding comment a reader does need; two runs per cell). Complied means a Fix or Ask finding deletes at least two of the three:

| framing | rule on | rule off |
|---|---|---|
| supportive | 2/2 | 2/2 |
| neutral | 2/2 | 2/2 |
| competing (focus on correctness) | 2/2 | 1/2 |
| total | 6/6 | 5/6 |

Every complying run flagged all three. One on-arm run also asked to delete or rewrite the needed rounding comment, because the repo rounds half up and the comment documents half even. The first grading missed cuts written without the word "comment"; the detector was fixed and the 12 rows regraded from their saved reports.

## Result

—

## Watch

—

## Back-out

Restore the Dead weight item in both code-reviewer files from the commit before this change.
