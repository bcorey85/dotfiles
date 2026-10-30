---
type: "Change"
change_type: "fixed"
title: "Review loop counts a finding row whatever order its keys come in"
description: "The review loop's stop hook now counts a log-review-finding call as a finding row wherever `kind=finding` stands in it, so a row logged with `root=` first is no longer reported as missing and logged a second time."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:17:32-05:00"}
seq: 341
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::LedgerRowsTest::test_a_finding_row_with_root_before_kind_counts_so_the_loop_is_not_told_to_log_it_again"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The stop hook reads every log-review-finding call's arguments and counts the calls whose `kind` is `finding`,
  wherever that key stands. Before, it counted only calls whose first argument was `kind=finding`.
- A `;`, `|` or `&&` inside a quoted argument does not end the call's arguments, so `desc="null; guard"` ahead of
  `kind=finding` still counts.
- A `kind=run` row with `root=` first still counts as no finding row.

## Evidence

- One review loop logged its finding rows with `root=<repo>` ahead of `kind=finding`. The stop hook counted none of
  them, told the loop its rows were missing, and the loop logged them again, so the review ledger holds each of that
  run's findings twice.

## Result

Against the code before this change, the new root-first test fails: the hook blocks with "only 0 per-finding". After
it, `test_review_loop_gate.py` and `test_handback.py` pass (256 tests) and ruff passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. A finding row with any key ahead of `kind=finding` then goes uncounted, and the loop logs it again.
