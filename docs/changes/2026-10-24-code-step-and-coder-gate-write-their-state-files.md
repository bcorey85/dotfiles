---
type: "Change"
title: "code-step and coder-gate write their state files atomically"
description: "save_state and both coder-gate writers write a temp file in the same folder and then replace the target, so a reader that polls during a wait never sees a half-written file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T06:39:37-05:00"}
seq: 8
kind: "fix"
components: ["script/code-step", "script/coder-gate"]
evidence: ["suite failure"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest.test_a_reader_polling_the_state_file_never_sees_a_partial_write"
unmeasured: ""
---

## Change

- New `script_utils.write_text_atomically`: write to a temp file in the target folder, then `os.replace`.
- `code_step.save_state` and both `coder_gate` writers use it.

## Evidence

A full suite run failed once under load: `after-coder` polled the state file while a late hook wrote it, read a partial file, and told the user to delete the state and run `start`. That loses the run's state. The test passed alone 3 of 3 times, so the defect is a race, not a logic error.

## Result

The new test and a second one (the old state file stays whole when a write fails midway) fail before the fix and pass after it.

## Watch

None. A fix with a test.

## Back-out

Restore `save_state` and the coder-gate writers to `write_text`.
