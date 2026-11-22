---
type: "Change"
change_type: "fixed"
title: "A test run outside a memory-capped scope is denied with the capped form"
description: "A test run a session starts outside a systemd memory-capped scope is denied with the capped form, so a runaway test dies alone at the cap and every other session on the machine survives."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:18:02-06:00"}
seq: 23
kind: "fix"
components: ["script/inline-interpreter-hint", "script/memory-cap-scope"]
evidence: ["tests", "judgment"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::KillTest::test_child_past_the_cap_is_killed_and_the_calling_shell_survives"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number reads it, because a killed test run leaves no log row."
---

## Change

The Bash PreToolUse hook `gates/inline_interpreter_hint.py` now also denies a call with a test step that runs outside a
memory-capped scope. The step test lives in `lib/memory_cap_scope.py`: a step that `check_scope.step_runs_tests` reads
as a test run (pytest, `-m unittest`, vitest, jest, npm test, `parallel_tests.py`, ...) or that runs `tests/run.sh`,
with no `systemd-run` wrapper before it. A step with `--help`, `-h`, `--version` or `-V` runs nothing and passes, and
so do searches, prints and edits that only name a runner (`grep pytest x`, `cat tests/run.sh`). The deny text gives the
capped form: `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0` before the test program.

Design: deny with the capped form, not a silent rewrite. A rewrite has to splice the prefix into a pipeline, a chain or
a `cd`, and a wrong splice changes what runs with no sign to the agent; a deny costs one retry and shows the agent the
form. The cap is 8G with no swap: the machine has 30 GB, other sessions hold about 7 GB, and a full `tests/run.sh`
passes under it, so a runaway is killed at a quarter of the memory and the rest of the machine keeps over 15 GB.
The check runs only where a scope can start (Linux, `systemd-run` on PATH, a user bus under `XDG_RUNTIME_DIR`), so a
Mac passes every call. It sits in an existing hook, so it adds no process; any error in it passes the call, as the hook
already does, and `CLAUDE_SKIP_HOOKS` skips it. A prefilter on the command text skips the `check_scope` import for a
command that names no test word.

The one old test case that used `python3 -m unittest` as an allowed module run now uses `python3 -m http.server`.

## Evidence

Hook time, median of 200 runs per form on this machine, alternating, canned payload: a test command 62.8 ms with the
change, 48.9 ms before it, 13.7 ms for a bare `python3 -I -c pass`; a non-test command (`git status --short`) 55.1 ms
with the change, 49.3 ms before it, 14.3 ms bare. The extra 6 to 14 ms is the import of the new module and, for a test
command, of `check_scope`.

The kernel log of the previous boot (2026-10-27 to 2026-10-29) holds no `Killed process` line, and the current boot's
log holds only the suspend-time "OOM killer disabled/enabled" lines. The 2026-11-22 crash is in the current boot with no
kernel kill line, so the log does not name what took the memory; the session's own record names a `python3 -m unittest`
run piped through `tail`.

## Result

`tests/scripts/test_memory_cap_scope.py`: 11 caught shapes and 12 passed shapes, the deny with the capped form, a machine
with no scope passing the call, unreadable input and the skip switch passing, and `KillTest`: a child that allocates
512 MB under `MemoryMax=64M` is killed and the calling shell prints that it is alive. The kill test skips where
`systemd-run --user --scope` cannot start.

## Watch

None: a denied call writes no log row.

## Back-out

Delete `lib/memory_cap_scope.py`, its import and the `elif` branch in `gates/inline_interpreter_hint.py`, and the test
file.
