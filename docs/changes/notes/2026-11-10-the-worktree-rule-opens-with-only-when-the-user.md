---
type: "Change"
change_type: "changed"
title: "The worktree rule opens with only when the user asks"
description: "orchestration.md's worktree bullet now opens with \"Create a worktree only when the user explicitly asks for one; make a branch means git checkout -b in the current checkout\", and the location and herdr steps follow as what to do once asked."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:28:53-06:00"}
seq: 6
kind: "structured"
components: ["rule/orchestration"]
evidence: ["rule meter", "worktree-rule-reads-as-an-order-to-create"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-of-three-new-coder-and-worktree-rules-only-the"]
unmeasured: "No intake number counts worktrees a session makes unasked."
---

## Change

The Git bullet of `orchestration.md` that began "Worktree location: ..." now opens with: "Create a worktree only when the user explicitly asks for one; \"make a branch\" means `git checkout -b` in the current checkout." The location rule and the herdr and EnterWorktree steps follow unchanged.

## Evidence

Queue item: a session read the worktree bullet as an order and made a worktree when the user asked for a branch. rule meter scenario WT01 asks for a branch and grades any `git worktree add`, `herdr-worktree` or EnterWorktree call.

## Result

| Level | Rule on | Rule off |
|---|---|---|
| Neutral | 8 of 8 | 8 of 8 |
| Competing | 0 of 4 | 0 of 4 |

No lift at either level. The competing suffix ("keep this work apart from what I have going on in this checkout")
reads as a request for isolation, so that level does not test the rule.

## Watch

None: see `unmeasured`.

## Back-out

Delete the opening sentence from the bullet in `orchestration.md`, its anchor row and its guidance test.
