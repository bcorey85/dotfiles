---
type: "Change"
change_type: "changed"
title: "Every push line pulls with rebase first"
description: "Push lines handed to the user no longer fail when another machine pushed first: every one runs pull --rebase before push."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T08:21:02-06:00"}
seq: 4
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-02: you HAVE to fix this issue its driving me actually insane"
proof: []
unmeasured: ""
---

## Change

The global CLAUDE.md rule on `!` lines now says every line that pushes runs `git -C <repo> pull --rebase` right before
`git -C <repo> push`.

## Evidence

A handed commit-and-push line was rejected because another machine had pushed to the same branch. The merge driver
already rebuilds the built change pages on a rebase, so pulling with rebase does not stop on them.

## Result

Push lines no longer fail on a moved remote.

## Watch

None: no intake number records a rejected push.

## Back-out

Delete the added sentence from `claude/.claude/CLAUDE.md`.
