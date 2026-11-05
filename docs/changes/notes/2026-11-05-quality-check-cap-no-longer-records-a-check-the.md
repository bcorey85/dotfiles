---
type: "Change"
change_type: "fixed"
title: "Quality-check cap no longer records a check the shell never found"
description: "quality_check_cap.py records nothing for a failed Bash run that exited 126 or 127, so a rerun after installing the missing tool or fixing its path is allowed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:14:56-06:00"}
seq: 1
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_command_not_found_records_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

New constant `NOT_STARTED_EXIT_CODES = (126, 127)`. On `PostToolUseFailure`, the gate returns without a record when the exit code is one of them, next to the existing signal-exit return. The docstring names the two codes. `test_a_plain_nonzero_exit_is_still_recorded` now uses 125 in place of 127.

## Evidence

judgment: a session's check failed with `command not found`; the cap then denied the rerun after the tool was on PATH, though the check never ran. The new test fails on the base commit and passes after. Hook median on a matching exit-127 event: 8.0 ms, next to 8.2 ms for a bare Python start (30 runs each).

## Result

`test_quality_check_cap.py` 98 of 98 pass; lint clean.

## Watch

—

## Back-out

Remove `NOT_STARTED_EXIT_CODES` and its check, restore 127 in the plain-exit test, and remove the new test.
