---
type: "Change"
change_type: "changed"
title: "Debug's fix step keeps one boundary-check line in place of a five-bullet list"
description: "Debug's fix phase replaces a five-bullet defense-in-depth lesson with one line: add a check at each boundary the bad value crossed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:53-06:00"}
seq: 12
kind: "user-rule"
components: ["skill/debug"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: until both arms run, this edit stays uncommitted. No intake number reads where debug adds checks."
---

## Change

`skills/debug/SKILL.md`, phase 4: the "Defense in depth" bullet and its four sub-bullets (entry, business logic,
environment guard, instrumentation) become "Where the bad value crossed layers, add a check at each boundary it passed,
so the class cannot recur."

## Evidence

prompt audit against Opus 5.5: the sub-bullets taught general engineering with no toolkit-specific rule, and pulled
toward multi-site fixes against the "one change" bullet above them.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Restore the bullet list.
