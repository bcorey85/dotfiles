---
type: "Change"
change_type: "fixed"
title: "A scoped test failure that fails the same way without the diff no longer stops the review loop"
description: "The review loop's scoped-tests gate now reruns each red command on HEAD without the diff, as the full check already does. When every failure is the same there, the packet records the scoped tests as a pre-existing failure and the loop goes on, so /code no longer stops to ask the user to confirm base failures. A failure new to the diff, a new failing test included, still stops as critical-blocker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T07:14:20-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop-script", "script/coder-gate", "script/full-check"]
evidence: ["judgment", "tests"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_scoped_failure_that_fails_the_same_way_on_head_without_the_diff_does_not_stop_the_loop"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code/coder_gate.py`: new `run_scoped_tests_with_failures` returns the scoped result, the tails and each real failure as (command, outcome, output). `run_scoped_tests` wraps it and keeps its two-value return.
- `review/full_check_gate.py`: new `FullCheckSteps.scoped_failures_pre_existing` runs each failing command through `full_check.base_run`, once per command per loop, and compares it with `full_check.is_pre_existing`. It reuses the full check's base worktree, live-tree cleanup and gate environment, and writes `scoped-head-<n>.log` and `scoped-base-<n>.log` in the loop folder.
- `review/full_check.py`: new result constant `SCOPED_PRE_EXISTING`.
- `review/review_loop_script.py` `run_test_commands`: a red run whose failures are all pre-existing sets `scoped_tests` to `SCOPED_PRE_EXISTING: <the run's result>` and goes on.

## Evidence

Bench run on a Django repo with failing tests on base: the scoped-tests gate stopped two phases in a row as critical-blocker. Each stop asked the user to confirm that the failures were base failures. They were the same failures on base. The user ruled that these questions are not theirs to answer.

## Result

Without the change, the named test fails: the base comparison does not exist, and the loop stops as critical-blocker. With the change, it passes. Its sibling test passes too: a new failing test on top of the old one still stops the loop. The existing panic-text test now fails only with the diff, so it still covers a real red run. `bash tests/run.sh`: 3305 tests, 0 failed.

## Watch

None. No intake field counts critical-blocker stops by cause.

## Back-out

Revert the commit.
