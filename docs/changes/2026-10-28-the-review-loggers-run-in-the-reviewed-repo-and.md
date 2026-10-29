---
type: "Change"
change_type: "fixed"
title: "The review loggers run in the reviewed repo and log the scoped reviewer's deferrals"
description: "log-review-finding and log-review-metrics take root=<path> and run there, so a review loop working on a sibling worktree logs against that worktree, and the cap exit's scoped reviewer defers its fix findings as source=scoped instead of being refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T19:40:14-05:00"}
seq: 210
kind: "fix"
components: ["script/log-review-finding", "script/log-review-metrics", "agent/review-loop", "shared/finding-log"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_log_review_finding.py::TestAuditRowTest::test_root_logs_a_run_on_a_dirty_tree_from_another_folder_with_a_base_of_the_form_ref_tilde_n"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `scripts/lib/_kv.sh`: new `kv_enter_root`. It enters the folder a `root=<path>` arg names, drops the arg, and
  refuses with exit 1 when the folder cannot be entered.
- `log-review-finding` and `log-review-metrics` call it before any git read, so HEAD, the dirty flag, the snapshot,
  the branch, `diff_base` and the repo `ledger write` derives all come from the reviewed repo. Both resolve their own
  folder to an absolute path, so the helper scripts still resolve after the `cd`.
- `log-review-finding`: a `diff_base` that names no commit is refused with the folder it looked in and a pointer to
  `root=`; "no merge-base" now prints only when there is none.
- `log-review-finding`: a deferred `fix` row with `source=scoped` logs. That is the one reviewer the cap exit
  dispatches on files a coder changed after the last full review; its findings get no coder by design, so the
  logger refused every row the loop was told to write for them.
- `agents/review-loop.md`: logger calls in Steps 7 and 7b take `root=<ROOT>` in place of `cd <ROOT> &&`; the scoped
  reviewer's findings log with `source=scoped actioned=deferred`. `skills/_shared/finding-log.md` names `root=` and
  the `scoped` source.

## Evidence

- Review loops on sibling worktrees ran the logger from the session folder, where the integration branch ref did
  not exist: every run row with `diff_base=<branch>` or `<branch>~3` was refused as "no merge-base with HEAD", and
  the finding rows that did log carried the session repo's branch, HEAD and snapshot.
- A scoped-reviewer finding logged as `actioned=deferred source=round` was refused, so its row was lost.
- Tests that fail on the base scripts and pass now:
  `test_log_review_finding.py::TestAuditRowTest::test_root_logs_a_run_on_a_dirty_tree_from_another_folder_with_a_base_of_the_form_ref_tilde_n`,
  `test_log_review_finding.py::TestAuditRowTest::test_a_root_that_cannot_be_entered_is_refused_and_no_row_is_sent`,
  `test_log_review_finding.py::TestAuditRowTest::test_diff_base_naming_no_ref_is_refused`,
  `test_log_review_metrics.py::LogReviewMetricsRepoTest::test_root_runs_the_writer_in_that_checkout_from_another_folder`,
  `test_ledger_write.py::LedgerWriteTest::test_a_deferred_review_loop_fix_row_is_logged_only_for_an_open_class_member_or_the_scoped_reviewer`.

## Result

- The three logger test files pass: 48 tests.

## Watch

- None: no intake counts refused logger calls.

## Back-out

- Revert the commit.
