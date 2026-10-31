---
type: "Change"
change_type: "changed"
title: "The branch-exit skill relies on the global two-run cap on quality checks"
description: "The branch-exit skill now relies on the global two-run cap on quality checks instead of repeating it, saving tokens on every invocation."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 28
kind: "behavior"
components: ["skill/branch-recap"]
evidence: ["judgment"]
watches: []
---

## Change

The branch-exit skill now relies on the global two-run cap on quality checks instead of repeating it. The cap applies across the whole task from the top-level rules.

## Evidence

judgment

## Result

The cap applies across the whole task from the top-level rules; a restatement adds tokens to every invocation and gives the rule a second place to drift

## Watch

—

## Back-out

—
