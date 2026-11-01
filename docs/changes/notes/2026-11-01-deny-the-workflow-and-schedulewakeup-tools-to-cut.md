---
type: "Change"
change_type: "removed"
title: "Deny the Workflow and ScheduleWakeup tools to cut the main prefix"
description: "settings.json denies the Workflow and ScheduleWakeup tools, so their inline schemas (about 3.7k tokens) leave every main session's first request."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T07:52:31-06:00"}
seq: 437
kind: "user-rule"
components: ["rule/settings-json"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-01: denying the Workflow and ScheduleWakeup tools (~3.7k). - yes do these."
proof: []
unmeasured: ""
---

## Change

`permissions.deny` in `claude/.claude/settings.json` adds `Workflow` and `ScheduleWakeup`. No agent, skill, command
or hook in the toolkit calls either tool. Dynamic `/loop` (no interval) and multi-agent workflows stop working until
the entries are removed.

## Evidence

Headless prefix difference runs: the Workflow schema is 1,979 tokens and the ScheduleWakeup schema 1,695, both
inlined rather than deferred.

## Result

Every main session's first request drops by about 3,674 tokens.

## Watch

None: no intake number reads the prefix size.

## Back-out

Remove the two entries from `permissions.deny`.
