---
type: "Change"
title: "The per-dispatch telemetry hook now records a mechanical yield proxy for agents that do not self-report"
description: "The per-dispatch telemetry hook now records a mechanical yield proxy for agents that do not self-report findings — the length of the returned report and whether it matches a found-nothing signature."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-14T00:00:00-05:00"}
seq: 1
components: ["script/log-agent-usage"]
evidence: ["census"]
watches: []
---

## Change

The per-dispatch telemetry hook now records a mechanical yield proxy for agents that do not self-report findings — the length of the returned report and whether it matches a found-nothing signature

## Evidence

census

## Result

Search and research dispatches carried a cost figure but no value signal, so the largest untracked spend could not be told apart from waste. The proxy lands on the same dispatches that already record token cost, captured from the returned report so nothing depends on the orchestrator remembering to log. It is deliberately a proxy: a terse correct answer scores low, so it flags only the clear tail — real cost spent on a trivial or empty-handed report — and the ambiguous middle still needs the transcript.

## Watch

—

## Back-out

—
