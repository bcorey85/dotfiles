---
type: "Change"
change_type: "changed"
title: "The review loop's stopping-rule receipt now requires naming each repaired finding"
description: "The review loop's stopping-rule receipt is now enforced in the packet instead of through a telemetry enum: answering \"nothing I repaired was class-shaped\" now requires naming each repaired finding and why it fits neither shape, and the bare word alone is reported as an unrun check."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 6
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review loop's stopping-rule receipt is now enforced in the packet instead of through a telemetry enum: answering "nothing I repaired was class-shaped" now requires naming each repaired finding and why it fits neither shape, and the bare word alone is reported as an unrun check

## Evidence

census

## Result

The enum's two main answers — a class closed by enumeration, and nothing class-shaped to close — were followed by a same-class escape in the same repo at rates that could not be told apart, so the field recorded a habit rather than a check, and a quarter of rows omitted it despite being told never to. The check itself stays: it is the only thing that has ever pushed a converged-looking round back into another correctness pass. Both retired fields are gone from the metrics call, the report's dial for them, and its field list.

## Watch

—

## Back-out

—
