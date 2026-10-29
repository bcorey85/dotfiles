---
type: "Change"
change_type: "changed"
title: "The refactor skill's test audit step dispatches the test reviewer with `model` omitted instead of a sonnet"
description: "The refactor skill's test audit step dispatches the test reviewer with `model` omitted instead of a sonnet override."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-16T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["skill/test-audit", "agent/test-reviewer"]
evidence: ["judgment"]
watches: []
---

## Change

The refactor skill's test audit step dispatches the test reviewer with `model` omitted instead of a sonnet override.

## Evidence

judgment

## Result

The agent is Opus-pinned and every measurement of it ran on Opus. A call-site override put it on a model no round measured, against the pinned-agent rule the model guard enforces. No run; the fix is one dispatch line.

## Watch

—

## Back-out

—
