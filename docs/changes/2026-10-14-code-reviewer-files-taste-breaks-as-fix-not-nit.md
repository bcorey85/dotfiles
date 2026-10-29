---
type: "Change"
change_type: "changed"
title: "`code-reviewer` files taste breaks such as dead code and single-use pass-throughs as `fix`, not `nit`"
description: "`code-reviewer` files taste breaks as `fix`, not `nit`: dead code, a single-use pass-through, a dense nested expression, a comment that restates the code or narrates its history, a test that asserts only an absence, a hand-written copy of a helper the file already has."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-14T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/code-reviewer", "skill/fix"]
evidence: ["sealed bench round"]
watches: ["code-reviewer-taste-as-fix"]
---

## Change

`code-reviewer` files taste breaks as `fix`, not `nit`: dead code, a single-use pass-through, a dense nested expression, a comment that restates the code or narrates its history, a test that asserts only an absence, a hand-written copy of a helper the file already has. Naming that obscures nothing and breaks no written rule stays `nit`. +51 words

## Evidence

sealed bench round

## Result

Work logs: a third of escapes since Aug 31 were caught by the user by hand, over half of them smell, duplication or test kinds. Four runs per arm on one change with seven planted taste defects: 28 of 28 at fix against 14 of 28 for the old text, 0 false fixes, other findings 14 against 11, Opus cache read median 144k against 202k and output 7.6k against 9.0k. A list of the repo's past user catches in the handoff matched the plants but halved other findings, so it was not built. Limit: the rule and the plants come from the same census.

## Watch

user catches of smell, duplication and test kinds in the next intake.

## Back-out

restore the old line, "Naming and dead weight that don't obscure intent and break no written rule → `nit`."
