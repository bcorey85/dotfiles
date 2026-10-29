---
type: "Change"
change_type: "fixed"
title: "Review loop records: crashed coders, metrics rows, run rows and test ledger writes come out right"
description: "A coder that dies mid-fix reports the files it changed, the metrics logger refuses a row it would store wrong, the stop hook blocks a stale or short metrics line and an unlogged nit and writes run rows for the reviewed repo, and no test can write to the real ledger."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:35:08-05:00"}
seq: 125
kind: "fix"
components: ["script/review-loop-script", "script/log-review-metrics", "script/review-loop-gate", "script/parallel-tests", "agent/review-loop", "skill/coder-core"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::LedgerRowsTest::test_a_metrics_line_whose_counts_differ_from_the_packet_is_blocked"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The scripted review loop: a coder call that fails after it edited the tree adds the files it changed to
  `files_touched`, and the failure names them and quotes the coder's reply. Before, `files_touched` came back empty.
- `log-review-metrics`:
  - It refuses an arg with no `=`, the tail of an unquoted `result=PASS WITH WARNINGS`, with exit 2 and no row.
  - A ledger row needs a `result=` from the verdict set. Any other value, or none, exits 2 and writes no row, with the
    telemetry switch on or off.
  - `diff_base=` is accepted and dropped.
  - The review-loop agent's metrics step quotes the result and names the set.
- The review-loop stop hook:
  - It blocks a metrics line logged before the last reviewer round, and one whose `fixed=` or `skipped_fp=` differs
    from the packet.
  - It blocks a nit that has no nit finding row.
  - A metrics call the logger refused does not count as logged.
  - It reads backslash-continued and chained calls.
  - It writes the run row in the repo the loop reviewed: the review-scope `ROOT=` line, else the prompt's `repo:` line.
    Before, it wrote the run row from the session cwd, which named the wrong repo and branch for a review of another
    worktree.
- Tests: importing `toolkit_paths` or `fake_ledger`, or running `tests/parallel_tests.py`, puts a `ledger` that always
  fails first on PATH and points CARGO_HOME at a folder with no ledger. A test run by hand can no longer write rows to
  the real ledger.
- coder-core: run a test file that takes minutes by test name, or in the background. Never run it whole in the
  foreground.

## Evidence

- Seven toolkit bug reports from review-loop runs. They include an empty `files_touched` after a coder that edited
  files died, metrics rows with cut or uncounted results, run rows naming the session's repo, and fake rows a
  hand-run test wrote to the real ledger.
- Each part has a test that failed before and passes after:
  - `tests/scripts/test_review_loop_script.py`:
    - `test_coder_that_dies_after_editing_reports_its_files_and_its_reply`
  - `tests/scripts/test_log_review_metrics.py`:
    - `test_an_unquoted_spaced_result_is_refused_and_writes_no_row`
    - `test_a_result_outside_the_verdict_set_or_missing_is_refused`
    - `test_diff_base_is_accepted_and_never_stored`
  - `tests/scripts/test_review_loop_gate.py`:
    - `test_a_metrics_line_logged_before_the_last_reviewer_round_is_blocked`
    - `test_a_metrics_line_whose_counts_differ_from_the_packet_is_blocked`
    - `test_a_nit_with_no_nit_row_is_blocked_even_when_the_row_total_matches`
    - `test_a_metrics_call_the_logger_refused_does_not_count_as_logged`
    - `test_a_review_of_a_worktree_outside_the_cwd_logs_that_worktrees_repo_and_branch`
  - `tests/scripts/test_toolkit_paths.py`:
    - `test_a_test_that_plants_no_stand_in_reaches_only_the_failing_guard`

## Result

- Review metrics rows carry a valid verdict and the packet's counts.
- Run rows name the repo and branch that were reviewed.
- A crashed coder's partial fix shows in the report.
- Tests can no longer write to the real ledger.

## Watch

No new watch. The fixes correct the rows that the review watches read; they add no behavior a metric measures.

## Back-out

Revert the commit. `repair()` also sets `last_pass = "coder"`, from a change merged in from master: keep that line
when reverting.
