---
type: "Change"
title: "Refuse a non-numeric int field before the ledger"
description: "log-review-finding and log-escape refuse an int field that is not a whole number, naming the pair, before any row is written. review-loop writes each logger call with literal key=value arguments, one call per row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T20:00:00-05:00"}
seq: 231
kind: "fix"
components: ["script/log-review-finding", "script/log-escape", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_review_finding.py::TestAuditRowTest::test_an_empty_or_non_numeric_int_field_is_refused_and_no_row_is_sent"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/lib/_kv.sh`: new `kv_require_whole_numbers <int_keys>`. After `kv_fold`, it refuses any listed key whose string value is not a whole number, prints each bad pair and how to call, and exits 1. JSON null passes.
- `log-review-finding` checks `iter line n_findings diff_loc`; `log-escape` checks `line`.
- `agents/review-loop.md`: each logger call is written out with literal key=value arguments, one call per row, never split from a string in a loop. The opencode port has no logger calls, so it is unchanged.

## Evidence

- A review-loop logged eight finding rows from a zsh loop over `set -- $r`. zsh did not split `$r`, so each call sent `line=`, and `ledger write` refused all eight with `field_kind_mismatch line`. Other sessions sent an empty or unexpanded `iter=`, `n_findings=` and `diff_loc=`.

## Result

- On the base scripts the new tests send the rows and fail. On this change the scripts refuse them with exit 1 and write nothing.

## Watch

—

## Back-out

Revert the commit. The ledger refuses a bad int field again with `field_kind_mismatch`.
