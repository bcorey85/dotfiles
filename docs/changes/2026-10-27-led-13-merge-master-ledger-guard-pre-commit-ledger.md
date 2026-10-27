---
type: "Change"
title: "LED-13: merge master; ledger guard pre-commit; ledger-write drops jsonl fallback; the review loop's agent-usage row writer removed"
description: "Merge master into the guard-migration branch. The pre-commit hook runs the ledger guard before the change-ledger gate. ledger-write no longer appends to a local file when ledger is missing: it prints one stderr line, drops the row and exits 0. The review-loop script no longer writes an agent-usage row. coder_gate rows carry timed_out again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T14:08:58-05:00"}
seq: 90
kind: "fix"
components: ["script/code-step", "script/coder-gate", "script/deferred-push-check", "script/ledger-write", "script/review-loop-gate", "script/review-loop-script", "skill/audit", "skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_write.py::LedgerWriteTest::test_no_ledger_drops_the_row_with_one_stderr_line_exit_0_and_no_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `.githooks/pre-commit` runs `.githooks/ledger-guard` first and refuses the commit when it exits non-zero, then runs
  the change-ledger gate. `.githooks/ledger-guard` is a byte-identical copy of the agent-ledger hook. With no `ledger`
  on PATH the commit is refused and the message names `cargo install --path ~/dev/agent-ledger`.
- `telemetry/ledger-write` drops the legacy jsonl fallback. With no `ledger` on PATH it prints one stderr line, drops
  the row and exits 0; no file is written. The stem-built file names and the repo-from-git fallback are gone.
- The comments of the writers that named the fallback file say the row is dropped. `/audit` review lane no longer
  mentions a local escapes file.
- The review loop's agent-usage row writer is removed from `review_loop_script.py`. `log_agent_usage.py` and its test
  stay as they are here and leave with the LED-13 retire patch, applied with `git am`.
- `script_utils.ledger_write(row_type, fields, label)` pipes a row to `telemetry/ledger-write`; a failed write prints
  one stderr line and returns without raising. `coder_gate.append_gate_log` and `code_step_core.record_dispatch_cause`
  use it in place of their own copies of the call.
- `review_loop_script.py` writes a `dispatch_cause` row (agent type coder, kind fix, one position token per finding
  (n1, n2, ... in the coder prompt's order), at most 32) before each fix coder dispatch. A failed write never stops the dispatch.
- `deferred_push_check.py` reads the branch's deferred bug and correctness review findings through one
  `ledger query --max-time 2` (no cache refresh, no retry, 5 s subprocess timeout), maps each `path_key` back to a file
  the branch changes, and lists `file:line (class)` without a description. With no ledger, a busy ledger or any
  ledger failure it exits 0 with no output. `REVIEW_FINDINGS_FILE` is no longer read. `script_utils.py` gains
  `query_ledger_rows_once`, `parse_tsv_rows` and `ledger_keys` for it.
- `coder_gate.py` writes `timed_out` (count of timed-out commands) on its `coder_gate` row, and result `timeout` when
  no command failed and one timed out.
- `log-review-check` runs `ledger worker --once` before its queries and asserts it exits 0.

## Evidence

- Before: `ledger-write` with no ledger appended rows to files under `~/.claude`; the review-loop script appended an
  agent-usage row; the coder gate row carried no `timed_out`; `log-review-check` failed 3 cases with "cache busy"
  (exit 75).
- `tests/scripts/test_pre_commit_hook.py`, `test_ledger_write.py`, `test_coder_gate.py`,
  `test_review_loop_script.py`, `test_review_loop_gate.py`, `test_deferred_push_check.py` and
  `skills/review/log-review-check` cover each path.

## Result

- See the run output of the tests named above.

## Watch

—

## Back-out

- Revert the commit.
