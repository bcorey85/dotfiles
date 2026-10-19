---
type: "Change"
title: "The global CLAUDE.md gets a code-layout rule under Engineering Judgment"
description: "The global CLAUDE.md gets a code-layout rule under Engineering Judgment."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-17T00:00:00-05:00"}
seq: 1
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

The global CLAUDE.md gets a code-layout rule under Engineering Judgment. Split a function into steps with one blank line between steps, keep a lookup next to the guard that checks it, return early in place of a nested `if`, put an inner call result in a named variable before it goes into a call that is itself an argument, and follow this even when the surrounding code is denser. +68 words in every main session and subagent

## Evidence

judgment

## Result

Effect unmeasured. The user reported dense code in a direct-coding session and asked for a fix that does not depend on project lint. The prompt names the two layout conventions it follows, code paragraphs and Extract Variable. A write-time hook for the same two shapes was tried and removed (see its row).

## Watch

—

## Back-out

delete the bullet
