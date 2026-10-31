---
type: "Change"
change_type: "fixed"
title: "Both files that synthesize the architect's ruled-out approaches now carry the architect's own count instead"
description: "Both files that synthesize the architect's ruled-out approaches now carry the architect's own count instead of asserting three."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 21
kind: "fix"
components: ["skill/eng-spec", "skill/eng-arch"]
evidence: ["census"]
watches: []
---

## Change

Both files that synthesize the architect's ruled-out approaches now carry the architect's own count instead of asserting three

## Evidence

census

## Result

The instruction that produces them allows fewer than three if it says so, and the template preserves that; the two files doing the synthesis had lost it, which pressures inventing a third — an invented alternative in a decision record reads later as one genuinely considered and rejected

## Watch

—

## Back-out

—
