---
type: "Change"
change_type: "changed"
title: "A lane session sends every user command to the session that started it"
description: "The global rules now say a lane session started by another session sends every command for the user, merge lines included, to that session, and a lane brief carries the starting session's current name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T09:34:09-06:00"}
seq: 9
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-07: tell agents they need to send you merge commands not me"
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/CLAUDE.md`, Safety Rails: the rule that only the main session hands the user a command now also
  covers lane sessions. A session that another session started sends every command for the user to that session
  with SendMessage and never shows one in its own pane. The session that writes a lane brief reads its own name from
  ListAgents and puts it in the brief.
- `docs/rule-anchors.md`: the Safety Rails row carries the new hash and links this change.

## Evidence

The user asked for it on 2026-11-07. A forked lane runs as its own interactive session, so "only the main session"
read as covering it. Lane briefs also named the starting session by a name it no longer had after a restart, so a
lane's report could not reach it, and the lane showed its merge line to the user instead.

## Result

Not measured. A user rule ships on the user's word.

## Watch

None. No intake number counts commands a lane shows to the user.

## Back-out

Revert the added sentences in Safety Rails and the anchor row.
