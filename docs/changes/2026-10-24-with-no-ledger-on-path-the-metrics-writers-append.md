---
type: "Change"
title: "With no ledger on PATH the metrics writers append to the old jsonl files"
description: "ledger-write exited 0 silently when the ledger binary was missing, so a machine with no ledger lost every review finding, review run, review metrics row, escape, spec run and scan run. It now appends the completed row to the jsonl file each type used before the ledger switch and prints one stderr line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T15:52:13-05:00"}
seq: 14
kind: "fix"
components: ["script/log-escape", "script/log-scan", "script/log-spec-run", "script/log-review-finding", "script/log-review-metrics", "script/review-scope", "script/review-loop-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_ledger_write.py::LedgerWriteTest::test_no_ledger_appends_the_completed_row_to_the_type_file_and_prints_one_stderr_line"
unmeasured: ""
---

## Change

`scripts/telemetry/ledger-write` holds the one map from row type to file. With `ledger` on PATH nothing changes. With no `ledger`, it appends one JSON line:

- `review_finding` and `review_run` go to `review-findings.jsonl`, with `kind` finding or run.
- `review_metrics` goes to `review-metrics.jsonl`.
- `review_escape` goes to `review-escapes.jsonl`.
- `spec_run` goes to `spec-runs.jsonl`.
- `scan_run` goes to `scan-runs.jsonl`.

- `review_scope` goes to `skill-usage.jsonl`, with `ts` and `via` `agent`.

It adds `date`, `schema_version`, `repo` and `session` the way the writers did before the switch. It writes `result` with spaces, as before the switch, and keeps ids, `head` and `dirty` as strings. A spec run row keeps its `slug` in the file. The ledger still does not get it. With HOME unset, the script drops the row with one stderr line. `file` and `branch` stay raw in the local file, and the work intake hashes them when it copies the file. It prints `ledger-write: ledger not on PATH; row appended to <file>`. A failed append prints one stderr line and exits 0, so a telemetry write never blocks the workflow. The callers still own the telemetry switch.

`review_loop_gate.py` no longer skips the review run row when `ledger` is missing. It passes on the writer's stderr line. If the append fails, the gate retries the row on the next stop. The writers' header comments and the audit review lane no longer say the jsonl files are frozen.

## Evidence

The work intake of 2026-10-23 says `ledger streams: not tracked (ledger not installed)`. Its newest review finding row is dated 2026-10-21, the day of the ledger switch. Every quality edit watch read from those streams was blind from that day on.

## Result

The fallback test fails on the old writer, which exits 0 with no file and no stderr, and passes on the new one. The gate test `tests/scripts/test_review_loop_gate.py::RunRowTest::test_a_run_row_goes_to_the_findings_file_while_ledger_is_off_path_and_is_written_once` fails before and passes after.

## Watch

None. The next work intake shows it: the review jsonl files get rows dated after 2026-10-24 while `ledger streams` says not tracked.

## Back-out

Revert the edits to `ledger-write` and `review_loop_gate.py`. The writers then drop rows again on a machine with no ledger.
