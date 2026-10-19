---
type: "Change"
title: "The Opus-pinned deep coder is removed"
description: "The Opus-pinned deep coder is removed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 5
components: ["agent/review-loop"]
evidence: ["model round"]
watches: []
---

## Change

The Opus-pinned deep coder is removed. On the deep modifier, the code skill, the review loop and the shared modifier rules dispatch the plain Sonnet coder

## Evidence

model round

## Result

After an Opus review, the Opus coder left 0.188 missed defects per run against 0.104 for Sonnet 5.5. Its only edge was 0.04 fewer failures per run before review, which the review removed. The agent listing loses one line on every main request

## Watch

—

## Back-out

—
