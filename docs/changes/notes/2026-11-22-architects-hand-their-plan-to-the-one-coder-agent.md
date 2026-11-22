---
type: "Change"
change_type: "fixed"
title: "Architects hand their plan to the one coder agent by name"
description: "Architect-core names the `coder` agent as the implementer in place of a `*-coder` family that no longer exists."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:52-06:00"}
seq: 6
kind: "user-rule"
components: ["skill/architect-core"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "A fact correction: the rule's wording and demand are unchanged, so no meter arm can differ. No intake number reads it."
---

## Change

`skills/architect-core/SKILL.md`: "You design; the matching `*-coder` implements." becomes "You design; the `coder`
agent implements."

## Evidence

prompt audit against Opus 5.5: `agents/` holds one `coder.md`, whose description says it has no frontend or backend
variant.

## Result

Applied. No run: fact correction.

## Watch

None: see `unmeasured`.

## Back-out

Restore the `*-coder` wording.
