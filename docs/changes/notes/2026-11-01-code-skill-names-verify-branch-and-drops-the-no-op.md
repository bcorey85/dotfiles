---
type: "Change"
change_type: "fixed"
title: "Code skill names verify-branch and drops the no-op deep modifier"
description: "/code now points at the skill that exists: its three `/verify` mentions read `/verify-branch`, and the `+deep` modifier, which changed nothing, is no longer offered."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:28:52-05:00"}
seq: 424
kind: "user-rule"
components: ["skill/code"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-01: after the overnight cut-candidate report: fix everything"
proof: []
unmeasured: ""
---

## Change

- `skills/code/SKILL.md`: `/verify` → `/verify-branch` in three places; the `+deep` mentions in the modifier line and step 1 go.

## Evidence

No `verify` skill exists; the branch-end check is `skills/verify-branch/`. `+deep` had no branch in the skill or its scripts.

## Result

Full dotfiles suite passes (2,923 tests, 0 failed).

## Watch

None.

## Back-out

Revert the commit.
