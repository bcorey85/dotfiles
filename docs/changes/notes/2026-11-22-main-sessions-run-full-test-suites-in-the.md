---
type: "Change"
change_type: "changed"
title: "Main sessions run full test suites in the background"
description: "The Bash hook denies a full test suite in the foreground of a main session and says to rerun it with run_in_background, so the conversation stays open while the suite runs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T17:08:23-06:00"}
seq: 35
kind: "user-rule"
components: ["script/inline-interpreter-hint", "script/memory-cap-scope"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "The rule is code in a hook, not prompt text, so the rule meter has no scenario for it. No intake number reads how long the conversation stayed blocked; the hook-fires count and the security block log show how often it denies."
---

## Change

`gates/inline_interpreter_hint.py` (the existing Bash PreToolUse hook) denies a main session's Bash call that runs a full test suite without `tool_input.run_in_background` true. The deny text says to rerun the same command with run_in_background true inside the memory cap, then go on or end the turn until the completion notice. Before: `bash tests/run.sh` ran in the foreground for up to 600 s with the conversation blocked. After: the call is denied once and the rerun with run_in_background true goes through.

`lib/memory_cap_scope.py`, `foreground_full_suite`: a step is a full suite when it runs `tests/run.sh`, `python -m unittest` with no module or with `discover`, or a runner `check_scope.direct_check_scope` reads as "whole" (bare `pytest`, `npm test`, `npx vitest run`, `tests/parallel_tests.py` with no file). A run of named files (`python3 -m unittest test_x`, `pytest tests/test_a.py`, `--help`) stays allowed in the foreground. A call with `agent_id` (a subagent) is never denied: the review loop's agents must run checks in the foreground, and `wait_loop_gate` denies their background jobs. Any error passes the call. The check sits in the same hook process, after the memory-cap deny; no new hook.

## Evidence

user request. One dotfiles session ran the full suite in the foreground twice with a 600 s timeout and the user had to background it by hand. The Bash payload's `tool_input.run_in_background` and top-level `agent_id` are read by `gates/wait_loop_gate.py` and its tests (`test_wait_loop_gate.py`), which confirms both fields reach a PreToolUse hook.

## Result

`tests/scripts/test_memory_cap_scope.py::ForegroundFullSuiteTest` (foreground full suite denied, background allowed, named-file run allowed, subagent allowed, no-test command allowed, malformed payload fails open). Against the old files the denial test fails with 10 errors (no deny emitted) and the other five pass; against the new files all 13 tests in the file pass. `test_a_machine_with_no_scope_passes_the_call` now sends run_in_background true, since a foreground suite is denied on any machine.

Full suite: `systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh` in the background passed, 5661 tests in 190 files, 0 failed. Lint on the three changed files passes.

Hook time, median of 40 runs per cell, load average about 4.5 (noisy): bare `python3 -c pass` 10.0 ms. Before to after: full suite in the foreground 46.6 to 53.2 ms; full suite in the background 48.0 to 46.8 ms; targeted file run 62.5 to 55.5 ms; a command that runs no tests (`git status --short`) 48.5 to 41.6 ms. The differences are inside the run-to-run noise (an earlier pass under heavier load gave 57 to 72 ms before and 48 to 75 ms after). The new check adds one `check_scope` import only on a command that names a test word, which the memory-cap check already imported.

## Watch

None: no intake number reads it.

## Back-out

Revert the commit.

