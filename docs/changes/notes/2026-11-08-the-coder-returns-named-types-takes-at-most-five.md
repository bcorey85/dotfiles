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

Rule-meter, 8 runs with the text and 8 without, under a brief that pulls the other way. Runs that kept to the rule: five parameters, 0 → 7 of 8; one-loop comprehension, 0 → 3 of 8; ternary argument, 8 of 8 in both; named return type, 0 of 8 in both, because the brief asked for values destructured in order. Finding: `agent-evals/findings/2026-11-08-the-readability-rules-move-the-coder-only-where-a.md`.

## Watch

None of its own; see `unmeasured`.

## Back-out

Remove the two added sentences and the named-type bullet, and restore the anchor row.
