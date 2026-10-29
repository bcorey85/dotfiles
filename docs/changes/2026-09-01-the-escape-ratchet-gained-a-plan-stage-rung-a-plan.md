---
type: "Change"
change_type: "changed"
title: "The escape ratchet now has a plan-stage rung for closing plan defects"
description: "The escape ratchet gained a plan-stage rung: a plan defect closes with one command added where spec finalization already runs commands, or with a rule in the criteria lint when the shape is mechanically detectable — and that rung is to be tried before \"nothing worth guarding\"."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 10
kind: "behavior"
components: ["shared/escape-ratchet"]
evidence: ["census"]
watches: []
---

## Change

The escape ratchet gained a plan-stage rung: a plan defect closes with one command added where spec finalization already runs commands, or with a rule in the criteria lint when the shape is mechanically detectable — and that rung is to be tried before "nothing worth guarding"

## Evidence

census

## Result

Two-thirds of plan-stage escapes closed nothing, which is what happens when every available rung assumes there is code to guard: a stale count in a spec has no illegal state to type out and no convention that would have stopped it. Unclosed plan defects recur in the next spec, because nothing about the next spec's authoring changed — two have already recurred verbatim. The logger accepts the new rung and the telemetry report now splits the rung distribution by which gate was missed, since the plan population and the code population have different rungs available.

## Watch

—

## Back-out

—
