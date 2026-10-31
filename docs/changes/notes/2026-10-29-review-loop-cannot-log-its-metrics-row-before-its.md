---
type: "Change"
change_type: "fixed"
title: "review loop cannot log its metrics row before its reviewer reports"
description: "A review loop's metrics row is refused while no reviewer has been dispatched or one is still open, so a loop can no longer log a row before its first reviewer reports."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T17:13:04-05:00"}
seq: 329
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::MetricsTimingTest::test_metrics_call_before_any_reviewer_dispatch_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

The review-loop gate now also runs before each review-loop shell call that names log-review-metrics. It denies that call while no reviewer has been dispatched, unless the loop runs in no-review mode, and while a reviewer the loop launched has not yet reported. The deny tells the loop to wait for the report and log the metrics line once, at Step 7, after the last reviewer reports. A loop that ends before any reviewer runs (setup fault, critical blocker, fix-first plan impact, empty scope) must still log a row, so while no reviewer has been dispatched the call passes when its `result=` field, read as a shell word, is `NOT DISPATCHED` (or `NOT_DISPATCHED`). The review-loop agent's Step 7 now says to log that result on such an exit. The pass-through ends at the first reviewer dispatch: after any dispatch the deny rules apply whatever `result=` says, and an unknown or missing `result=` before dispatch stays denied.

## Evidence

judgment: one /review run logged fix=0, fixed=0, result=PASS before it dispatched its reviewer; the reviewer then found a fix. The stop-time check only asked for a second row after the hand-back, which left the wrong row in the ledger.

## Result

A metrics call before any reviewer is dispatched, or while one is open, is denied; a call once a reviewer has been dispatched and none is open passes. Before dispatch, a call with `result=NOT DISPATCHED` also passes, so a no-review exit logs its row; the same call while a dispatched reviewer is still open is denied.

## Watch

None.

## Back-out

Remove the Bash PreToolUse registration of the review-loop gate in `settings.json` and, in `review_loop_gate.py`, the Bash branch in `main()`, `metrics_deny_reason`, `check_metrics`, `METRICS_EARLY_REASON`, `METRICS_OPEN_REASON`, `NO_REVIEW_METRICS_RESULTS`, the no-review `result=` sentence in Step 7 of `agents/review-loop.md`, the `NO_REVIEW_MODE` and `metrics_calls` imports, and the PreToolUse (Bash) paragraph in the module docstring. `NO_REVIEW_MODE` moved from `handback.py` to `loop_transcript.py` (`handback.py` now uses `loop_transcript.NO_REVIEW_MODE`), so the back-out must restore it in `handback.py` if it removes it from `loop_transcript.py`. Also remove the matching EXPECTED_FILTERS entry in `tests/scripts/test_hook_if_filters.py`, `LoopTranscript.open_kinds` in `loop_transcript.py` (its only caller is the gate), and the `MetricsTimingTest` class in `tests/scripts/test_review_loop_gate.py`.
