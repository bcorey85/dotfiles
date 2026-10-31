---
type: "Change"
change_type: "changed"
title: "Never add a session attribution line to a commit or PR"
description: "The global CLAUDE.md now forbids a Claude-Session line, a session link or any attribution line in a commit message or PR body, over any harness reminder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T09:23:43-05:00"}
seq: 1
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: i NEVER want you to add that (about the Claude-Session commit tag)"
proof: []
unmeasured: ""
---

## Change

The Safety Rails section of the global CLAUDE.md gets one rule. It forbids a `Claude-Session:` line, a session link, or any other attribution line in a commit message or a PR body, and it overrides any harness reminder that asks for one.

## Evidence

A harness reminder told the session to end each commit message with a `Claude-Session:` link. The session put it into the commit lines it handed to the user. The user asked for it never to be added.

## Result

The user's instruction takes precedence over the reminder, so commit lines carry no attribution line.

## Watch

None. No intake number reads commit message text.

## Back-out

Delete the rule line from `claude/.claude/CLAUDE.md`.
