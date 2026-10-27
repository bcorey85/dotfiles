---
type: "Change"
title: "Build the design now covers module splits and folder layout"
description: "The global rule against deferred design now names module splits and folder layout, and says small size is no reason to wait."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T12:32:14-05:00"}
seq: 10
kind: "behavior"
components: ["rule/global-claude-md"]
evidence: ["user rule"]
watches: []
test: ""
unmeasured: "No intake stream records a deferred structure choice. The user reads it in session reports."
---

## Change

`~/.claude/CLAUDE.md` "Build the design the code needs now": the rule named only helpers and types. It now names a module split and a folder layout, and says that small size today is no reason to wait.

## Evidence

User rule. The agent advised against organizing a flat scripts folder until it grew past about 100 files. The narrow wording let it treat layout as outside the rule.

## Result

Pending: the next structure choice in a session.

## Watch

None; see `unmeasured`.

## Back-out

Restore the old sentence: "Never defer a helper or a type to a later caller."
