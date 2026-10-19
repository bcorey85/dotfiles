---
type: "Change"
title: "The mutation verdicts are now read from the agent that defines them instead of summarized at the call site"
description: "The mutation verdicts are now read from the agent that defines them instead of summarized at the call site, with only the two easily-misread ones spelled out."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 27
components: ["skill/test-audit"]
evidence: ["census"]
watches: []
---

## Change

The mutation verdicts are now read from the agent that defines them instead of summarized at the call site, with only the two easily-misread ones spelled out

## Evidence

census

## Result

The summary had dropped the precondition the defining agent requires before a mutant may be called survived. Inert while the text only consumes verdicts, and a trap the moment it is reused anywhere that produces one

## Watch

—

## Back-out

—
