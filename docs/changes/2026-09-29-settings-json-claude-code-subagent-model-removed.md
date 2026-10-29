---
type: "Change"
change_type: "removed"
title: "settings.json: the general-purpose and catch-all agents inherit the main model again, with `CLAUDE_CODE_SUBAGENT_MODEL` removed"
description: "settings.json: the general-purpose and catch-all agents inherit the main model again; `CLAUDE_CODE_SUBAGENT_MODEL` is removed the same day that it was added."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 7
kind: "behavior"
reverts: "2026-09-29-settings-json-claude-code-subagent-model-set-to"
components: ["rule/settings-json", "agent/general-purpose"]
evidence: ["judgment"]
watches: []
---

## Change

settings.json: the general-purpose and catch-all agents inherit the main model again; `CLAUDE_CODE_SUBAGENT_MODEL` is removed the same day that it was added

## Evidence

judgment

## Result

The user removed the line. Nothing ran under it that a round measured

## Watch

—

## Back-out

—
