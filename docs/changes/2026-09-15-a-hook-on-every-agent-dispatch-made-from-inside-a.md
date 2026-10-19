---
type: "Change"
title: "A hook on every agent dispatch made from inside a subagent forces the dispatch to run in the foreground"
description: "A hook on every agent dispatch made from inside a subagent forces the dispatch to run in the foreground."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-15T00:00:00-05:00"}
seq: 1
components: ["script/agent-foreground"]
evidence: ["controlled replay"]
watches: []
---

## Change

A hook on every agent dispatch made from inside a subagent forces the dispatch to run in the foreground. Dispatches from the main session are untouched. Bypass: the documented skip variable.

## Evidence

controlled replay

## Result

The agent tool defaults to background, and a subagent cannot wait on a background agent: the completion notice goes to the main session. So the review loop dispatched its reviewer, got a launch stub, and returned prose or a waiting line instead of a packet. In one week of live sessions every one of the loop's nested dispatches ran in the background. With the hook, the unchanged loop collected its reviewer and returned a valid packet in one replay of the round's control tree at the same cost as before. Four probe runs confirmed the nested-caller marker and the input rewrite in both directions.

## Watch

—

## Back-out

—
