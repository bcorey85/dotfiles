---
type: "Change"
change_type: "fixed"
title: "failing-test lines skip log lines and ignore traceback line numbers"
description: "Failing-test extraction ignores logger lines and keeps unittest FAIL:/ERROR: headers and pytest FAILED lines; head and base logs that differ only in traceback line numbers read as pre-existing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 6
kind: "fix"
components: ["script/check-output"]
evidence: ["fix-gate-packet-reports-error-log-lines-as-failing", "scoped-test-gate-still-stops-on-base-tree-failures"]
watches: []
test: "tests/scripts/test_check_output.py::CheckOutputTest::test_logger_lines_beside_a_real_failure_are_not_failing_tests"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/check_output.py` drops logger lines (`ERROR django.request ...`, `ERROR: message`) from the failing-test lines,
and `normalized_log_line` strips the line number from a Python traceback frame line.

## Evidence

The fix-gate packet listed log lines as failing tests. The scoped-test gate stopped on base-tree failures whose
traceback line numbers had shifted with the edit.

## Result

New tests in `test_check_output.py` and `test_full_check.py`.

## Watch

None.

## Back-out

Revert the commit.
