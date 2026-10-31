---
type: "Change"
change_type: "changed"
title: "Bash hooks start 5-10 ms faster: check_scope loads its Makefile and pytest config readers only when it judges make or pytest"
description: "check_scope imports makefile_text and pytest_config inside the two functions that use them, so quality_check_cap and coder_gate stop paying about 8 ms of imports on every Bash, Edit and Write call."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:55:58-05:00"}
seq: 2
kind: "fix"
components: ["script/check-scope", "script/quality-check-cap", "script/coder-gate"]
evidence: ["bench timing"]
watches: []
test: "tests/scripts/test_check_output.py::HookStartImportTest::test_importing_check_output_leaves_the_makefile_and_pytest_config_readers_unloaded"
asked: ""
proof: []
unmeasured: "edit_watch reads dated rows; hook-latency.txt is a one-shot bench per intake, so the next intake's quality-check-cap median is read by hand against 105-116 ms."
---

## Change

`lib/check_scope.py` imports `makefile_text` (which pulls `dataclasses` and `inspect`) inside `scan_make`, and
`pytest_config` (which pulls `tomllib` and `configparser`) inside `pytest_testpaths`. Every other caller of
`check_scope` and `check_output` imports them as before. No hook's event, matcher or command changes.

## Evidence

Bench timing, 15 runs per payload. `check_scope` import 14.8 → 7.0 ms. Per hook: `quality_check_cap.py` 42 → 32 ms,
`coder_gate.py bash-hook` 41 → 31.5 ms, next to a bare Python start of 8.6 ms (work machine: 20 ms). Parallel hook
set, median wall: Bash PreToolUse 57.5 → 52.5 ms, Bash PostToolUse 46.6 → 36.4 ms, Edit PostToolUse 73.5 → 64.9 ms.

## Result

The test fails against the previous `check_scope.py` (both readers load on import) and passes after. `bash tests/run.sh`
in the worktree: 5006 tests in 116 files, 0 failed, lint clean.

## Watch

None in edit-watches.json. Read `quality-check-cap.py` in the next intake's `data-ingest/hook-latency.txt`: 105-116 ms
before, about 90 ms predicted.

## Back-out

Revert the commit; the two imports move back to the top of `check_scope.py`.
