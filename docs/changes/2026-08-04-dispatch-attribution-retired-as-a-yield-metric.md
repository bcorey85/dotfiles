---
type: "Change"
change_type: "removed"
title: "Agent usage logging no longer reports dispatch attribution as a yield metric"
description: "Dispatch attribution is no longer reported as a yield metric, because it measures routing and not yield."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["script/log-agent-usage"]
evidence: ["metric audit"]
watches: []
---

## Change

Dispatch attribution is no longer reported as a yield metric. Before, it was reported as one.

## Evidence

metric audit

## Result

Measures routing, not yield

## Watch

—

## Back-out

—
