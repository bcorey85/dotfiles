---
type: "Change"
title: "The plan reviewer now batches its tree checks: it lists the plan's claims first and settles every independent"
description: "The plan reviewer now batches its tree checks: it lists the plan's claims first and settles every independent check in the same turn, taking a new turn only for a check that depends on the previous result."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 15
components: ["agent/plan-reviewer"]
evidence: ["token census"]
watches: []
---

## Change

The plan reviewer now batches its tree checks: it lists the plan's claims first and settles every independent check in the same turn, taking a new turn only for a check that depends on the previous result.

## Evidence

token census

## Result

Its cost was turns, not commands: nearly every turn issued a single command and re-read a context that ended above a hundred thousand tokens, so cache reads were almost all of its input. Expected to roughly halve per-run tokens; not yet measured.

## Watch

—

## Back-out

—
