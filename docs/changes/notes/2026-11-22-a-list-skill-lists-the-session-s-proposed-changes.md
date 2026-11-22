---
type: "Change"
change_type: "added"
title: "A /list skill lists the session's proposed changes as one numbered list"
description: "A new /list skill turns the changes proposed in a session into one numbered list, broken things first, with a ship gate per item, so the user picks by number."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:47:15-06:00"}
seq: 5
kind: "user-rule"
components: ["skill/list"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: no meter scenario grades a slash-command list format yet, so the skill stays uncommitted until the user rules on shipping it unmeasured. No intake number reads it."
---

## Change

New `skills/list/SKILL.md`. Reads only changes already proposed in the conversation, orders them broken → conflict →
stale text → flags, prints one numbered line each with `path:line`, the change and a ship gate (direct, meter, user), and
ends with a pick-by-number line.

## Evidence

user request after a `/doctor prompt-audit` run produced a 29-finding report and the user asked for the changes as an
ordered list.

## Result

Pending: no meter fixture for this output shape.

## Watch

None: see `unmeasured`.

## Back-out

Delete `skills/list/`.
