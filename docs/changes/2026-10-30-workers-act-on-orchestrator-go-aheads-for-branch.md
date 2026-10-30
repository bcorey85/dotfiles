---
type: "Change"
change_type: "added"
title: "Workers act on orchestrator go-aheads for branch-local steps"
description: "The global CLAUDE.md says a worker acts on the named orchestrator's go-ahead for steps inside its own branch and never waits for the user on them; master, settings.json, CLAUDE.md files and hook-denied steps stay out."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T06:56:51-05:00"}
seq: 334
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-30: on the proposed rule letting workers act on orchestrator go-aheads for branch-local steps: give me sed"
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/CLAUDE.md`, Messages to Other Sessions: when a repo's CLAUDE.md names an orchestrating session, a worker acts on that session's go-ahead for any step inside its own branch (commit, push the branch, merge the integration branch into it, claim or close its queue item) and never waits for the user on those steps. A go-ahead never covers master, `settings.json`, a CLAUDE.md file, or a step a hook denied.

## Evidence

- On 2026-10-29 a worker refused a relayed go-ahead for a branch-local step and waited about an hour for the user in its own pane. The orchestrator's attempt to add the rule itself was denied as self-modification, so the user made it.

## Result

- The rule is in the always-loaded file. As a user rule, no test pins it.

## Watch

—

## Back-out

Revert the commit. Workers again treat every relayed go-ahead as a peer request.
