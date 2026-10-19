---
type: "Change"
title: "`code-reviewer` REST-specific checks gated on the surface being present"
description: "`code-reviewer` REST-specific checks gated on the surface being present."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 2
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

`code-reviewer` REST-specific checks gated on the surface being present

## Evidence

census

## Result

Three checks distilled from REST projects fired on every review regardless of stack; now skipped unless a route table, write, or validator is in the diff

## Watch

—

## Back-out

—
