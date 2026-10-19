---
type: "Change"
title: "settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` set to `sonnet`"
description: "settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` set to `sonnet`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 6
components: ["rule/settings-json", "agent/general-purpose"]
evidence: ["judgment"]
watches: []
---

## Change

settings.json: `CLAUDE_CODE_SUBAGENT_MODEL` set to `sonnet`. The general-purpose and catch-all agents run on Sonnet 5.5 in place of the Opus main model. Agents with a pinned model, a model given at dispatch, and the built-in Explore and Plan agents do not change

## Evidence

judgment

## Result

Untested. Every named agent pins its model, so only unpinned dispatches move. Compare their token use by model in the next census

## Watch

—

## Back-out

—
