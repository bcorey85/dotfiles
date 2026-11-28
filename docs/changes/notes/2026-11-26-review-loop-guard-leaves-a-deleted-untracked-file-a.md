---
type: "Change"
change_type: "fixed"
title: "review loop guard leaves a deleted untracked file a finding or the fix coder record names"
description: "The untracked-file guard no longer puts back a stray untracked file that a finding of the pass names for deletion or that the fix coder record shows the loop wrote."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-26T12:00:00-06:00"}
seq: 15
kind: "fix"
components: ["script/review-loop-untracked", "script/review-loop-ruled-out"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_coder.py::UntrackedDeletionTest::test_an_untracked_file_a_finding_names_for_deletion_stays_deleted_when_the_diff_lists_no_such_file"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `review/review_loop_ruled_out.py` `begin_pass` reads a finding's deletion over the diff's files and every untracked file, so a stray untracked file the diff does not list (outside the review scope, or in the plan folder) is deletable when a finding names it. Before, only the diff's files were read, and the guard put the file back so the finding came back open.
- `review/review_loop_untracked.py` `guarded_untracked` leaves out the paths of the `fix_coder_written` record, so a file the loop's fix coder wrote stays deletable after the process that held `LOOP_WRITTEN` ended. The record lists the paths the fix coders wrote since the run's last `--new-run` or HEAD change.
- An untracked file a holder row proves held (`coder_held_files`) is never deletable, whether a finding names it or the record lists it. `begin_pass` and `begin` both take that set, and `claude_call_reply` passes it to `begin`; `claude_call` takes no held set, since no caller of it has one. A held file with no holder row may still go to the coder.
- A deletion nobody asked for is still restored and noted: `test_an_untracked_file_no_finding_names_is_restored_and_noted_when_a_finding_names_another`.

## Evidence

- judgment: a reviewer finding asked the fix coder to delete a stray untracked file, the coder did, and the guard put it back twice in two runs.

## Result

`test_an_untracked_file_a_finding_names_for_deletion_stays_deleted_when_the_diff_lists_no_such_file` and `test_a_file_the_fix_coder_record_names_stays_deleted_after_the_loop_state_is_lost` fail on the tree before the change ("True is not false": the file was restored) and pass after.

## Watch

Read the next review packet's `tool_fault` for "deleted untracked files" on a file a finding named. A file a person makes at a path the record lists is treated as the coder's until the next `--new-run`.

## Back-out

Restore the `diff_files` loop in `begin_pass`, drop the `coder_written` subtraction in `guarded_untracked` and the `fix_coder_written` read.
