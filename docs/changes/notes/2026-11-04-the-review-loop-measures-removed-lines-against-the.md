---
type: "Change"
change_type: "fixed"
title: "The review loop measures removed lines against the commit it started on"
description: "The removed-lines guard pins HEAD when the loop starts and diffs against that commit after every coder pass, so a commit of the change while reviewers run no longer reads as a fix pass that removed the change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 9
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_commit_of_the_change_while_reviewers_run_does_not_read_as_a_fix_that_removed_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

`change_under_review` moves from `review_loop_script.py` to `review_loop_plan.py`, which owns `scope` and `base_scope`, as `lines_added_since(repo, start)`. A HEAD still at `start` diffs against HEAD with renames followed, as before; a moved HEAD diffs against `start` through `base_scope`. The new class `ChangeUnderReview` pins `start` at loop start and holds `added` and `removed()`. `LoopRun.change` replaces `change_added`, so the script adds no state field and drops from 996 to 966 lines. `files_touched` still counts another session's edits in the worktree: that part of the report stays open.

## Evidence

judgment: a session committed the change under review while reviewers ran; the packet stopped with "the fix passes removed 1496 of the 1595 source lines" though the files were intact. The new test commits mid-loop and fails on the base commit with the fix-removed-change stop, and passes after.

## Result

`test_review_loop_script.py` 222 of 222 pass; lint clean.

## Watch

—

## Back-out

Move `change_under_review` back into `review_loop_script.py`, restore `change_added`, remove `ChangeUnderReview`, and remove the test.
