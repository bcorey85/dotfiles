---
type: "Change"
title: "SIGTERM test treats a vanished pid as killed"
description: "The process-alive helper in the SIGTERM test returns dead when the pid leaves /proc between the signal check and the stat read."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T14:22:53-05:00"}
seq: 272
kind: "fix"
components: []
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_is_running_reports_a_pid_that_vanishes_after_the_signal_check_as_dead"
asked: ""
proof: []
unmeasured: "Test-only change; no intake number reads a test helper."
---

## Change

The test helper that reports whether the grandchild is still running checked `/proc/<pid>/stat` with `exists()` and then read it. A process exiting between the two raised FileNotFoundError. The old helper also treated a missing stat file as running, and the single read now handles both cases. The helper now reads once and treats a missing file as dead. A new test calls it with a reaped pid while the signal check is stubbed to succeed.

## Evidence

Judgment. The new test failed against the old helper, which reported a pid with no /proc entry as running; it passes with the fix.

## Result

The SIGTERM test passed 20 of 20 repeated runs, and the whole test file passes.

## Watch

None. A recurrence shows as a failure in the suite.

## Back-out

Revert the helper and delete the added test in `tests/scripts/test_review_loop_script.py`.
