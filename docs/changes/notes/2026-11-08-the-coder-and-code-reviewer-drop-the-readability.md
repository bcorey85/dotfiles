---
type: "Change"
change_type: "removed"
title: "The coder and code reviewer drop the readability lines that changed nothing"
description: "coder-core loses the ternary-argument sentence and the code reviewer's fix list loses its four newest entries; each scored the same with and without the text, and the hand-back readability check still enforces all four limits in code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T21:59:11-06:00"}
seq: 13
kind: "user-rule"
components: ["skill/coder-core", "agent/coder", "agent/code-reviewer"]
evidence: ["user rule", "removal round"]
watches: []
test: ""
asked: "2026-11-08: cut both"
proof: []
unmeasured: "A removal of text that scored at ceiling in both arms; the hand-back check keeps the limits, so no intake number moves."
---

## Change

- `skills/coder-core/SKILL.md`, `## Readability comes first (HARD RULE)`: removes "A ternary is a whole assignment's value, never a call argument."
- `agents/code-reviewer.md`, `### Step 3: Structure`: the taste-break fix list drops a ternary passed as a call argument, a comprehension with two loops, a returned tuple of three or more values, and a non-test function with more than five parameters.

## Evidence

Rule-meter, 8 runs with the text and 8 without, under a brief that pulls the other way. The coder kept ternaries out of call arguments in 8 of 8 runs in both arms. The reviewer marked the planted readability smells as a fix in 8 of 8 runs in both arms. Finding: `agent-evals/findings/2026-11-08-the-readability-rules-move-the-coder-only-where-a.md`.

## Result

Both texts are gone. The hand-back readability check still refuses all four patterns in code.

## Watch

None; see `unmeasured`.

## Back-out

Restore the sentence and the four list entries, and restore the two anchor rows.
