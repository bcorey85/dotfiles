---
type: "Change"
change_type: "changed"
title: "Hand the user one chained command line, not a series"
description: "The global CLAUDE.md now tells the session to give the user one `!` line that chains every command with &&, in place of a series of lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T09:28:38-05:00"}
seq: 2
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: stop giving me 40000000000 commands to run in series"
proof: []
unmeasured: ""
---

## Change

The Safety Rails section of the global CLAUDE.md gets one rule. When the user must run git or shell commands, the session gives one `!` line that chains them with `&&`.

## Evidence

The session handed the user up to seven `!` lines to send one at a time, because the input box runs only the first line of a paste. The user asked for this to stop.

## Result

A hand-over is one line. A failed step stops the chain, so no later step runs on a bad state.

## Watch

None. No intake number reads hand-over text.

## Back-out

Delete the rule line from `claude/.claude/CLAUDE.md`.
