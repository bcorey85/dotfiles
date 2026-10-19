---
type: "Change"
title: "The finalization phase now dry-runs each phase's verification criteria before any coder is dispatched"
description: "The finalization phase now dry-runs each phase's verification criteria before any coder is dispatched: a static lint plus running the read-only commands against the pre-implementation tree."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-13T00:00:00-05:00"}
seq: 4
components: ["skill/eng-spec", "script/spec-criteria-lint"]
evidence: ["census"]
watches: []
---

## Change

The finalization phase now dry-runs each phase's verification criteria before any coder is dispatched: a static lint plus running the read-only commands against the pre-implementation tree

## Evidence

census

## Result

The automated-verification commands were authored at plan time and not run until branch end, so two failure shapes invisible on the page cost a whole branch: a command that errors on a bad or duplicate flag and runs zero checks, its pass condition never reachable; and a criterion already green before a line is written, unable to tell done from not-done. Both recurred across phases of one plan. The static half also flags a plan that assigns test-file writes to the implementing coder, which its own ownership gate denies, and a verification command naming an artifact a later decision retired.

## Watch

—

## Back-out

—
