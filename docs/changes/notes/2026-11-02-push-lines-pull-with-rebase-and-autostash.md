---
type: "Change"
change_type: "changed"
title: "Push lines pull with rebase and autostash"
description: "Push lines handed to the user run pull --rebase --autostash, so uncommitted edits in unrelated files no longer stop the line before the push."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T12:20:00-06:00"}
seq: 8
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-02: Every line that pushes runs `git -C <repo> pull --rebase` right before `git -C <repo> push`: another machine pushes to the same branch."
proof: []
unmeasured: ""
---

## Change

The global CLAUDE.md push-line rule says `git -C <repo> pull --rebase --autostash` in place of `pull --rebase`. The rule-anchor row for `## Safety Rails` carries the new hash.

## Evidence

The first push line written to the earlier rule stopped after its merge: `pull --rebase` refused because the checkout held uncommitted edits in unrelated files. The same line with `--autostash` then pushed, and the edits survived.

## Result

Push lines go through in a dirty checkout. git-discipline-gate still denies autostash in Claude's own Bash calls; the rule covers only lines the user runs. After the pull, autostash reapplies the edits unstaged.

## Watch

None: no intake number records a stopped push line.

## Back-out

Drop `--autostash` from the rule in `claude/.claude/CLAUDE.md` and restore the anchor row's hash and text.
