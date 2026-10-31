---
type: "Change"
change_type: "changed"
title: "The write-time prose check gained a second pass reporting hardcoded absolute paths and machine-specific names"
description: "The write-time prose check gained a second pass reporting hardcoded absolute paths and machine-specific names written into an agent, skill or command file."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 11
kind: "behavior"
components: ["script/dead-prose-gate"]
evidence: ["judgment"]
watches: []
---

## Change

The write-time prose check gained a second pass reporting hardcoded absolute paths and machine-specific names written into an agent, skill or command file. It warns and never blocks.

## Evidence

judgment

## Result

Those files are meant to be portable, and the failure is invisible at the moment of writing — it surfaces on another machine, as a rule that silently refers to nothing. Warn-only follows the precedent of the check already in that slot: the signal is useful and imperfect, so a human triages each hit rather than having a write refused.

## Watch

—

## Back-out

—
