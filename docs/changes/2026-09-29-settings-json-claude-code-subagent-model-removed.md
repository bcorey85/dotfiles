---
type: "Change"
change_type: "removed"
title: "settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` removed, the same day that it was added"
description: "settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` removed, the same day that it was added."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 7
kind: "behavior"
reverts: "2026-09-29-settings-json-claude-code-subagent-model-set-to"
components: ["rule/settings-json", "agent/general-purpose"]
evidence: ["judgment"]
watches: []
---

## Change

settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` removed, the same day that it was added. The general-purpose and catch-all agents again inherit the main model

## Evidence

judgment

## Result

The user removed the line. Nothing ran under it that a round measured

## Watch

—

## Back-out

—
