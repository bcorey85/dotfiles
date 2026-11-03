---
type: "Change"
change_type: "fixed"
title: "check_output reads a macOS framework Python missing-path line"
description: "check_output reads a macOS framework Python's \"can't open file\" line, which names the interpreter by its full path ending in MacOS/Python, as a missing-path check-command error."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T09:05:52-06:00"}
seq: 4
kind: "fix"
components: ["script/check-output"]
evidence: ["macOS suite run"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_step_on_a_missing_path_is_a_check_command_error_not_a_failure"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/check_output.py` `MISSING_PATH_LINES`: the python pattern accepts any non-space prefix and a capital `P`, so `.../MacOS/Python: can't open file ...` matches.

## Evidence

On macOS framework Python, a step on a missing script was classed as a test failure, not a check-command error.

## Result

Before: a missing path under macOS Python read as a failure. After: it reads as a check-command error, as on Linux.

## Watch

None: the test above pins it on a macOS run of `bash tests/run.sh`.

## Back-out

Revert the commit.

