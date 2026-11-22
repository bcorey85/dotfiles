---
type: "Change"
change_type: "added"
title: "Add toolkit-writing skill and load it in retro"
description: "Adds a toolkit-writing skill of eight checks for agent-read text, has the audit retro lane load it and read the environment, makes retro queue only the picks the user names, and rewrites the audit and debug skills to its checks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:25:54-06:00"}
seq: 21
kind: "user-rule"
components: ["skill/toolkit-writing", "skill/audit", "skill/debug"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "No rule-meter arms run yet: the retro, audit, debug and toolkit-writing wording is unmeasured until bin/rule_meter.py run-all covers it."
---

## Change

- `skills/toolkit-writing/SKILL.md`: new. Terms (no-op, duplicate, cache, sprawl, weak pointer, sediment, dense rule) and eight
  checks: description as trigger with no steps, `disable-model-invocation`, done-when lines, lead with the action, exactness matched to fragility, one default, order by use,
  prune. Rule cuts go through rule-meter first.
- `skills/audit/retro.md`: loads toolkit-writing first; new Read-the-environment step (unwired checks, missing
  guardrails, steering files over 150 lines); classify before placing a fix; a numbered report of at most 7, and
  queueing only the numbers the user picks; ledger tools replace agent-memory.
- `skills/audit/SKILL.md`: `disable-model-invocation`, Skill and ledger tools allowed, shorter boundaries.
- `skills/debug/SKILL.md`: a done criterion per phase, routing in one place, red flags collapsed.
- agent-evals: `bin/toolkit_skills.txt` lists the skill; CLAUDE.md points rule writing at it.

## Evidence

- user request: the user asked for an in-house version after a review run of mattpocock/skills writing-for-agents
  over four toolkit skills.

## Result

Not measured; see `unmeasured`.

## Watch

None.

## Back-out

Delete `skills/toolkit-writing/` and its line in `agent-evals/bin/toolkit_skills.txt`; revert the audit and debug
files from git.
