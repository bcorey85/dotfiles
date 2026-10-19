---
type: "Change"
title: "The security reviewer's prompt is its contract only (541 words"
description: "The security reviewer's prompt is its contract only (541 words, was 732): each of the eight scope classes is one line with no example lists, and the \"two real findings beat twelve\", \"#1 false positive\", \"not a softener\", \"highest-stakes class\", owner-name, and routing-reason clauses are gone."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 7
components: ["agent/security-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The security reviewer's prompt is its contract only (541 words, was 732): each of the eight scope classes is one line with no example lists, and the "two real findings beat twelve", "#1 false positive", "not a softener", "highest-stakes class", owner-name, and routing-reason clauses are gone. The suppress rule, the bar, the process, and the output block stay.

## Evidence

removal round

### Anchor reasons

Anchor `agents/spec-questions.md`, section `## Process` (evidence: unproven):

Six steps: create the directory, snapshot the source with the move-not-copy rule and the never-overwrite rule, read it fully, generate five to twelve questions ordered foundational to surface, write the file, return only the path and a count. Never varied.

## Result

A seeded HTTP-server diff with an IDOR, a path traversal, a shell injection, a logged token, and an unauthenticated config dump, plus a clean twin. Both texts caught all five bugs in every run and filed none of the three safe look-alikes. On the clean twin each text filed one hypothetical non-loopback finding in one run; the short text tagged it a design decision. Tokens were about equal (1.06x for the short text, driven by one extra missing-regression-test finding per run).

## Watch

—

## Back-out

—
