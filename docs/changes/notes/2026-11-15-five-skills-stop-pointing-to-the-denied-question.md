---
type: "Change"
change_type: "removed"
title: "Five skills stop pointing to the denied question tool"
description: "Six steps in five skills no longer tell the session to use AskUserQuestion, which settings.json denies; each step asks in plain text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T16:56:08-06:00"}
seq: 8
kind: "user-rule"
components: ["skill/peer-review", "skill/vault-progress", "skill/triage", "skill/refactor", "skill/eng-arch"]
evidence: ["six-skill-steps-call-askuserquestion-which"]
watches: []
test: ""
asked: "2026-11-15: asked by the user"
proof: []
unmeasured: "The user ruled no meter run: the edit only deletes the name of a tool no session can call."
---

## Change

- Removed the `AskUserQuestion` mention from six steps: `peer-review/SKILL.md` (next-step offer), `vault-progress/SKILL.md` (the pointed questions), `triage/SKILL.md` (hand-off offer), `refactor/SKILL.md` (design-decision route), and `eng-arch/SKILL.md` (ADR target pick and the section accept/keep/edit choice). Each step still asks; it just names no tool.
- Removed `AskUserQuestion` from the `allowed-tools` list of those five skills.

## Evidence

`permissions.deny` in `claude/.claude/settings.json` has denied `AskUserQuestion` since 2026-09-14, so every session met a step that named a tool it could not call. Found by reading; queue item `six-skill-steps-call-askuserquestion-which`.

## Result

No run. The user asked for the removal with no test on 2026-11-15.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit.
