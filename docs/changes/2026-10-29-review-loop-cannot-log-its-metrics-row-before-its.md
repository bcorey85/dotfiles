---
type: "Change"
change_type: "fixed"
title: "review loop cannot log its metrics row before its reviewer reports"
description: "A review loop's metrics row is refused until a reviewer has reported, so the ledger no longer holds a clean-looking row for a run whose reviewer later found a fix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T17:13:04-05:00"}
seq: 281
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

The review-loop gate now also runs before each shell call a review loop makes. It denies a call to the metrics logger while no reviewer has been dispatched, unless the loop runs in no-review mode, and while a reviewer the loop launched has not yet reported. The deny tells the loop to wait for the report and log the metrics line once, with the final counts, just before it hands back.

## Evidence

judgment: one /review run logged fix=0, fixed=0, result=PASS before it dispatched its reviewer; the reviewer then found a fix. The stop-time check only asked for a second row after the hand-back, which left the wrong row in the ledger.

## Result

An early metrics call is denied; a call after the reviewer reports passes.

## Watch

None.

## Back-out

Remove the Bash PreToolUse registration of the review-loop gate in `settings.json` and its Bash branch in `review_loop_gate.py`.
