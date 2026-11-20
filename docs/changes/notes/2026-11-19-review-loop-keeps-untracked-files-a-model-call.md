---
type: "Change"
change_type: "fixed"
title: "review loop keeps untracked files a model call deletes"
description: "Every reviewer and coder call in the review loop is wrapped by a guard that backs up untracked files and puts back any it did not create, with a tool_fault note naming the call."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:11-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["review-loop-deletes-untracked-files-in-the"]
watches: []
test: "tests/scripts/test_review_loop_script.py::SkipLabelsTest::test_a_main_session_reviewer_round_gets_a_deleted_untracked_file_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

The new `review/review_loop_untracked.py` snapshots the untracked files before each model call (`lib/file_backup.py`
copies files to disk, so large files survive) and restores any the call removed. The tool_fault note names the call
that removed it. The reviewers of one round run concurrently, so one guard covers the whole batch and a deletion is
noted against `review<N>-reviewers(<roles>)`, never against one reviewer. An untracked file deleted under a finding that names the deletion stays deleted.

## Evidence

A review run removed an untracked file it did not create; the remover was a model call, not `full_check.py`.

## Result

Tests in `test_review_loop_coder.py`, `test_file_backup.py` and `test_review_loop_script.py`. The check, gate and
format commands stay unguarded, as the plan states.

## Watch

None.

## Back-out

Revert the commit.
