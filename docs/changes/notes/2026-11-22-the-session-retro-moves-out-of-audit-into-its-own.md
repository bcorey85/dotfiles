---
type: "Change"
change_type: "changed"
title: "The session retro moves out of audit into its own hillclimb skill"
description: "The lane that reads one session and queues environment fixes becomes its own skill, typed as /hillclimb in place of /audit retro; its steps are unchanged, and /audit keeps the usage, skills and review lanes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T22:47:38-06:00"}
seq: 39
kind: "user-rule"
components: ["skill/hillclimb", "skill/audit"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: the user found the two-word command tiresome to type and picked a one-word name for the session retro"
proof: []
unmeasured: "A rename with the same steps: no work-log number moves. Both skills set disable-model-invocation, so neither description loads into context."
---

## Change

- `skills/audit/retro.md` moves to `skills/hillclimb/SKILL.md` with its text unchanged. The new file adds
  frontmatter (`disable-model-invocation: true`, the ledger search and session tools), `$ARGUMENTS` under Input, and
  the one boundary line that applied to it from the audit skill: every change to a skill, agent or log is the
  user's call, and the skill queues the candidates it judges worth a fix and logs each one it queued or skipped.
- `skills/audit/SKILL.md` drops the retro row, its synonym routing (postmortem, what went wrong) and its clause in
  the boundary line, and drops the ledger search and session tools, which only the retro lane used.

No rule is added or reworded, so no rule-meter run applies.

## Evidence

- user request: the user asked for a shorter command and chose the name.

## Result

`/hillclimb` lists as a user-invocable skill in a live session. `/audit all` already ran usage, skills and review
only, so its output does not change.

## Watch

None: see `unmeasured`.

## Back-out

Move `skills/hillclimb/SKILL.md` back to `skills/audit/retro.md`, drop its frontmatter, and restore the three audit
lines.
