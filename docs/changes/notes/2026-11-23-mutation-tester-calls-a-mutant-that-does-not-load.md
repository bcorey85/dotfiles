---
type: "Change"
change_type: "changed"
title: "Mutation tester calls a mutant that does not load INDETERMINATE, never killed"
description: "The mutation tester compiles the mutated file before it reads the test run; a mutant that breaks import or compile is INDETERMINATE, so a false kill no longer hides a test gap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T10:44:33-06:00"}
seq: 4
kind: "structured"
components: ["agent/mutation-tester"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-23-mutation-tester-calls-an-unloadable-mutant"]
unmeasured: "No intake number reads mutation-tester verdicts, so no edit watch can read this change at work. Stacks with no run: every stack except Django (pytest) and TypeScript (vitest)."
impact: {"metric": "quality", "before": 56, "after": 100, "unit": "% of unloadable mutants called INDETERMINATE (of 16 runs)", "finding": "2026-11-23-mutation-tester-calls-an-unloadable-mutant", "better": "higher"}
---

## Change

`agents/mutation-tester.md` Step 3 gains a first classify bullet: compile the mutated file with the stack's own check;
if that fails, or the run shows a collection, import or syntax error, the verdict is `INDETERMINATE — mutant does not
load`, never KILLED. A kill needs a test the baseline ran to fail on an assertion or a runtime error.

## Evidence

Rule meter, two fixtures, competing level, Sonnet, 8 runs per arm on each, smoke runs excluded.

## Result

Mutation tester calls an unloadable mutant INDETERMINATE in 16 of 16 runs with the rule, against 9 of 16 without
(56% → 100%):

- Django (pytest, IndentationError at collection): on 8/8, off 3/8 (5 KILLED).
- TypeScript (vitest, syntax error at transform): on 8/8, off 6/8 (2 KILLED).

Cost per run is flat across arms. Stacks with no run: all others.

## Watch

None: no intake number reads mutation-tester verdicts.

## Back-out

Delete the INDETERMINATE load-check bullet from Step 3 of `agents/mutation-tester.md` and restore its anchor row.
