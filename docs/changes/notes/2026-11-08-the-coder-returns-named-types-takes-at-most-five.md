---
type: "Change"
change_type: "changed"
title: "The coder returns named types, takes at most five parameters, keeps ternaries out of call arguments and comprehensions to one loop"
description: "coder-core's readability section gains four limits: a ternary is a whole assignment's value, never a call argument; a comprehension has one loop; a named type replaces a returned tuple of three or more values; past five parameters a function takes one named object."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T19:34:10-06:00"}
seq: 10
kind: "user-rule"
components: ["skill/coder-core", "agent/coder"]
evidence: ["user rule", "toolkit code census"]
watches: []
test: ""
asked: "2026-11-08: yes and add the 4 rules"
proof: []
unmeasured: "Read by the readability-first findings watch, which the first readability change owns."
overlap: "coder-readability-first-findings and coder-readability-first-coder-cost belong to the first readability change of the same day; this edit widens the same section and moves the same counts, so the two are read together."
---

## Change

`skills/coder-core/SKILL.md`, `## Readability comes first (HARD RULE)`: the plain-version bullet adds "A ternary is a whole assignment's value, never a call argument. A comprehension has one loop." A new bullet: return a named type (dataclass, NamedTuple, interface) in place of a tuple of three or more values; past five parameters, pass one named object.

## Evidence

User rule. A scan of the toolkit's own 106 non-test Python scripts (1,482 functions) found the patterns the first rule set did not name: 53 comprehensions with two loops or a nested comprehension, 32 functions with more than five parameters, 29 functions returning a tuple of three or more values with the shape told only in a comment, and ternaries inside call arguments among 372 ternaries.

## Result

Pending. A headless on-off check of the first readability section showed the prompt text alone did not stop a 43-line function in one pair; the hand-back check carries the enforcement.

## Watch

None of its own; see `unmeasured`.

## Back-out

Remove the two added sentences and the named-type bullet, and restore the anchor row.
