---
type: "Change"
title: "The review loop's gate-critical block now names both exits that may mark the commit gate clean, not just one"
description: "The review loop's gate-critical block now names both exits that may mark the commit gate clean, not just one, and says why the second qualifies."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 19
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review loop's gate-critical block now names both exits that may mark the commit gate clean, not just one, and says why the second qualifies

## Evidence

census

## Result

It listed only the convergence exit while the wrapper that actually runs the mark also runs it on the deferral exit — a rule about when commits may proceed, contradicted by the file that operates it. The deferral exit repairs every blocker first and logs the remainder for branch exit, which is what makes it a normal completion

## Watch

—

## Back-out

—
