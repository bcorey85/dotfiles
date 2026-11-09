---
type: "Change"
change_type: "changed"
title: "The code reviewer marks ternary arguments, two-loop comprehensions, wide tuples and six-parameter functions as fix"
description: "The code reviewer's taste-break fix list gains the coder's four new readability limits: a ternary passed as a call argument, a comprehension with two loops, a returned tuple of three or more values, and a non-test function with more than five parameters."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T19:34:10-06:00"}
seq: 11
kind: "user-rule"
components: ["agent/code-reviewer", "agent/smell-reviewer"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-08: yes and add the 4 rules"
proof: []
unmeasured: "The intake counts findings by class, not the nit-to-fix share within a class."
---

## Change

`agents/code-reviewer.md`, the structure disposition paragraph: four entries join the taste breaks that are a `fix`, matching the coder's new readability limits.

## Evidence

User rule; the same toolkit code census as the coder change.

## Result

Pending.

## Watch

None; see `unmeasured`.

## Back-out

Remove the four entries and restore the anchor row.
