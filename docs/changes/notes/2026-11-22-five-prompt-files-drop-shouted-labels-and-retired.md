---
type: "Change"
change_type: "changed"
title: "Five prompt files drop shouted labels and retired-step narration"
description: "Shouted labels and history narration come out of five prompt files, so Opus 5.5 reads each rule at its real weight. The rules themselves are unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:08:23-06:00"}
seq: 2
kind: "user-rule"
components: ["agent/frontend-architect", "skill/refactor", "agent/general-purpose", "skill/audit", "skill/adr"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: until both arms run for each reworded block, this edit stays uncommitted. No intake number reads how strongly a label weights a rule."
---

## Change

- `agents/frontend-architect.md`: heading `## CRITICAL: Pattern Consistency — Reuse Before Creating` becomes
  `## Pattern consistency: reuse before creating`; "The most important rule. Before designing ANY component:" becomes
  "Before designing any component:".
- `skills/refactor/SKILL.md`: the `CRITICAL:` heading label and the two "CRITICAL" references to the test rule go.
- `agents/general-purpose.md`: the two NEVER/ALWAYS file-creation lines become plain imperatives with the same content.
- `skills/audit/review.md`: step 1c, which existed only to print that it was retired, is deleted; the catches bullet
  keeps "do not report either" for the retired fields and drops the history clause.
- `skills/_shared/adr-template.md`: the line-cap bullet loses its threat wording ("hard — if you blow it") and names
  the script that enforces the caps. The caps stay: `adr_flow.py finish` checks them.

## Evidence

user request after a `/doctor prompt-audit` run against Opus 5.5: shouted labels make that model over-apply a rule,
and narration of retired steps spends tokens on every load.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Revert the five files to the previous dotfiles commit.
