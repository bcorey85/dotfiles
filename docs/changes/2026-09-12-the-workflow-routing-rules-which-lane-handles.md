---
type: "Change"
change_type: "changed"
title: "The workflow-routing rules — which lane handles which kind of work, when to delegate"
description: "The workflow-routing rules — which lane handles which kind of work, when to delegate, which review path a change takes — left the always-loaded instruction file and are now injected at session start, into the main session only."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["rule/global-claude-md", "rule/orchestration"]
evidence: ["judgment"]
watches: []
---

## Change

The workflow-routing rules — which lane handles which kind of work, when to delegate, which review path a change takes — left the always-loaded instruction file and are now injected at session start, into the main session only.

## Evidence

judgment

## Result

That content is addressed to whoever routes the work, and it was being paid for in every subagent invocation as well, where it is inert. Injection also reaches a session that has just compacted, which a file read at the start of the conversation does not. The cost is that nothing notices if the injection silently stops: the health script is the only detector, and it has to be run on purpose.

## Watch

—

## Back-out

—
