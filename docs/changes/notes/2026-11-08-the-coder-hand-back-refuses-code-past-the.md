---
type: "Change"
change_type: "added"
title: "The coder hand-back refuses code past the readability limits"
description: "A new gate check, readability_check.py, lists each non-test function a change wrote that nests control flow past two levels, runs past 40 lines, chains a ternary or passes a call result into a call that is an argument. /code sets it for every phase; a hit denies the coder's hand-back, and in the review loop's scoped re-run it goes to a coder pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T19:16:31-06:00"}
seq: 8
kind: "user-rule"
components: ["script/coder-gate", "script/review-loop-script", "script/gate-commands", "script/code-review-start"]
evidence: ["user rule", "stdlib and npm calibration"]
watches: ["coder-readability-first-findings", "coder-readability-first-coder-cost", "coder-readability-handback-denials"]
test: ""
asked: "2026-11-08: how do i tune my coder rules so that readability and human maintainability are king / #1 priority bar none ... go hard and solve this"
proof: []
unmeasured: ""
---

## Change

`scripts/code/readability_check.py --base <phase base>` reads the added lines of `git diff -U0` plus every untracked file, skips test files, and checks each function that holds an added line. Python goes through `ast`; TS and JS go through `readability_ts.mjs` with the project's `typescript` package, else the global one. A file with no typescript, or one that does not parse, is skipped. Git failure fails open with a stderr note.

Limits: control flow nested more than 2 levels on an added line (an else-if stays at its if's level; a nested function is its own record); a function over 40 own lines that the change wrote half of or took past 40; a chained ternary on an added line; a call result passed into a call that is itself an argument, on an added line. The report prints at most 10 `path:line function — limit (value): fix` lines.

Wiring: `gate_commands.py` appends the command with HEAD as base, so `coder_gate.py set` runs it at hand-back, where exit 1 is a real failure inside the 3-deny cap. `code_review_start.phase_gate_commands` appends it on all three branches (plan phase, whole plan, planless). The review loop leaves it out of the scoped tests and runs it as a hit check before stale prose: hits go to a `coder-readability` pass, then the full check and scoped tests run again. `run_stale_prose_check` became `run_hit_check`, shared by both checks.

## Evidence

User rule. Calibration, every line counted as added, 1,000 functions each: Python stdlib 153 fire (old gate 54), npm packages 86 fire (old gate 16). At a nesting limit of 3 the nesting fires would be 57 stdlib and 8 npm; the limit stays at 2 to match coder-core. Measuring own lines less nested functions cut npm length fires from 127 to 81.

## Result

Median of 11 runs on a 10-file change (7 stdlib .py, 3 npm .js, 8,688 lines): 240 ms, against 8 ms for `python3 -c pass`; the 7 Python files alone take 118 ms. Suite: `bash tests/run.sh` passes.

## Watch

`coder-readability-first-findings`: smell, duplication, complexity and naming findings per review run, good direction down. `coder-readability-first-coder-cost`: Sonnet coder cache read per dispatch, good direction flat; a denied hand-back adds a coder turn. `coder-readability-handback-denials`: readability denials per gated coder dispatch, good direction down; it reads the gate log's `readability_failed` count, so it starts with the rows written after that field shipped.

## Back-out

Drop the readability command from `gate_commands.main` and `code_review_start.phase_gate_commands`, and the readability pass from `review_loop_script.scoped_tests_pass`.
