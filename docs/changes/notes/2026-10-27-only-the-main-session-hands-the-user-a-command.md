---
type: "Change"
change_type: "changed"
title: "Only the main session hands the user a command"
description: "The global rules now say a subagent never writes a command for the user to run; it reports the step it could not do to its caller, which runs it or hands it on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T13:40:37-05:00"}
seq: 93
kind: "user-rule"
components: ["rule/global-claude-md", "agent/mutation-tester"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-10-27: tell your workers to never pass me commands. all need to route though you"
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/CLAUDE.md`, Safety Rails: after the one-`!`-line rule, a new paragraph says only the main session
  hands the user a command. A subagent names the step it could not do, and why, in its report to its caller, and the
  caller runs it or hands it on. Subagents load this file, so the rule reaches every agent.
- `claude/.claude/agents/mutation-tester.md`, Step 4: a blocked lock removal prints the command for the caller to
  run, not for the user.
- `docs/rule-anchors.md`: both rows carry their new hashes and link this change.

## Evidence

The user asked for it on 2026-10-27. The one-`!`-line rule above it read as an instruction to any agent, so a subagent
that met a step it could not do wrote a command addressed to the user.

## Result

Not measured. A user rule ships on the user's word.

## Watch

None. No intake number counts commands a subagent addresses to the user.

## Back-out

Delete the new paragraph in Safety Rails and restore "for the user to run" in the mutation tester's Step 4.
