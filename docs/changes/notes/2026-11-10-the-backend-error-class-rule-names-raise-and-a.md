---
type: "Change"
change_type: "changed"
title: "The backend error-class rule names raise and a built-in Python error, so the coder follows it in Python too"
description: "The error line in the path-scoped rules/backend.md is reworded from 'never a bare Error' to name raise and ValueError: the coder now uses the repo's error class in 8 of 8 Django runs, up from 3 of 8."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T23:08:53-06:00"}
seq: 7
kind: "structured"
components: ["rule/backend"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-with-the-rule-tester-isolated-two-of-three-backend"]
unmeasured: "No intake number reads this behavior: work escape descriptions are hashed, so no class count maps to the rule. Stacks with no run: React and Vue. One task per stack, Sonnet only, plain prompt only."
---

## Change

`rules/backend.md`, error line. Before: "Throw the repo's own error type with its error code; never a bare Error."
After: "Raise or throw the repo's own error class with its error code; never a built-in one such as Error or
ValueError."

## Evidence

Rule meter, with the line in the file that ships and the live path globs. The old wording named only the JavaScript
class, and on a Python task the coder raised `ValueError` whether or not the rule was loaded.

## Result

Runs in which every raise or throw used the repo's error class with a code, with the rule file vs without, Sonnet
coder, 8 runs per arm:

| Wording | Django | TypeScript backend |
|---|---|---|
| Old | 3 vs 2 | not rerun |
| New | 8 vs 1 | 6 of 6 graded vs 0 of 8 |

Two TypeScript runs with the new wording were not graded because the coder moved the checks into a shared helper;
the one read by hand throws the repo's class there.

Cost on Django, Sonnet, per task with the rule against without: about 1,900 more output tokens and 37,000 more
cache-read tokens, from reading the repo's error module.

## Watch

None: see `unmeasured`.

## Back-out

Restore the old line in `rules/backend.md` and the old hash in its anchor row.
