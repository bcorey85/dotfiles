---
type: "Change"
change_type: "changed"
title: "The readability hand-back check reads Vue script blocks and enforces the four new limits"
description: "readability_check.py reads the <script> and <script setup> blocks of .vue files at their own line numbers, and refuses a ternary passed as a call argument, a comprehension with two loops or a nested one, a returned tuple of three or more values, and a new def with more than five parameters."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T19:43:01-06:00"}
seq: 12
kind: "user-rule"
components: ["script/coder-gate", "script/review-loop-script"]
evidence: ["user rule", "stdlib and npm calibration"]
watches: ["coder-readability-first-findings", "coder-readability-first-coder-cost"]
test: ""
asked: "2026-11-08: yes and add the 4 rules"
proof: []
unmeasured: ""
---

## Change

`scripts/code/readability_check.py` and `readability_ts.mjs`. A `.vue` file goes to the TS helper, which keeps each `<script>` block's text and blanks every other character, so hit lines are the `.vue` file's lines; any block with `lang="ts"` (or tsx, jsx) sets that script kind, else JS. Template expressions are not read. A `.vue` file with no script block has no records.

Four new limits, each on added lines only, test files skipped, in the same `path:line function — limit: fix` report:
- a ternary that is directly a call argument, positional or keyword: "Assign it to a named variable first.";
- a Python comprehension or generator with two or more `for` clauses, or one holding another: "Write the outer loop as a for statement.";
- `return a, b, c` in Python, or `return [a, b, c]` in TS in a function with a tuple return type or none (arrow expression bodies too): "Return a dataclass, NamedTuple or interface.";
- a function whose def line is added and that takes more than five parameters, self, cls and a TS `this` left out, `*args` and `**kwargs` counted, a destructured object counted once, names starting with `test` left out: "Pass one named object."

## Evidence

User rule, with the toolkit code census of the coder-core change: 53 comprehensions with two loops or a nested one, 32 functions over five parameters, 29 functions returning a 3+ tuple in 1,482 functions.

Calibration, every line counted as added, 1,000 functions each. Python stdlib (email, http, json, logging, importlib): length 77, nesting 126, chained ternary 0, deep call 16; new: ternary argument 1, comprehension 2, tuple return 7, parameters 23; any limit 171 (153 before), any new limit 33. npm (eslint rules, ajv, hono, minimatch, debug): length 81, nesting 24, chained ternary 0, deep call 2; new: ternary argument 15, comprehension 0, tuple return 0, parameters 1; any limit 98 (86 before), any new limit 16. No new limit passes 2.3%.

## Result

Median of 11 runs on a 10-file change (5 stdlib .py, 3 npm .js, 2 real `<script setup lang="ts">` .vue files, 6,611 lines): 227 ms, against 8 ms for `python3 -c pass`. A sweep over every `.vue` file under `~/dev` outside node_modules parsed 7,859 of 7,859. Suite: `bash tests/run.sh` passes.

## Watch

The first readability check's watches: `coder-readability-first-findings` (review findings per run, good direction down) and `coder-readability-first-coder-cost` (coder cache read per dispatch, good direction flat; a denied hand-back adds a coder turn).

## Back-out

Revert the two files: drop `.vue` from `TS_SUFFIXES`, the `argternary` and `comp` rows of `LINE_LIMITS`, the `wide` loop and `parameter_hits`, and the helper's `vueScript`, `argternary`, `wide` and `params` fields.
