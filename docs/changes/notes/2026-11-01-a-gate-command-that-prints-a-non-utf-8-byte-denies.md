---
type: "Change"
change_type: "fixed"
title: "A gate command that prints a non-UTF-8 byte denies the hand-back"
description: "A coder gate command whose output holds a byte that is not UTF-8 now denies the hand-back with its output, in place of crashing the hook open."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:49:52-06:00"}
seq: 432
kind: "fix"
components: ["script/coder-gate", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_a_failing_command_that_prints_a_byte_that_is_not_utf_8_denies_with_its_output"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts hook crashes on bad bytes."
---

## Change

`script_utils.run_process` decodes the command's output with `errors="replace"`, so a byte that is not UTF-8 reads as U+FFFD.

## Evidence

judgment: a bug hunt reproduced a `UnicodeDecodeError` in the coder gate hook. The hook exited 1, which Claude Code treats as non-blocking, so the coder handed back with no verdict and no stamp.

## Result

The failing command denies the hand-back, and the summary records the run.

## Watch

—

## Back-out

Revert the commit.
