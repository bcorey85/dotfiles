---
type: "Change"
change_type: "added"
title: "suite_receipt dirty stops a merge into a checkout that holds changes the merge touches"
description: "A pre-merge check names the staged or unstaged files the branch's merge would touch, prints the fix, exits 3 and starts no merge."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-26T12:00:00-06:00"}
seq: 16
kind: "fix"
components: ["script/suite-receipt"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_suite_receipt.py::DirtyCheckTest::test_a_staged_deletion_and_a_dirty_page_the_merge_touches_stop_it_with_the_fix"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`tools/suite_receipt.py` gets a `dirty <repo> <branch>` verb. It lists the files `git diff HEAD` shows changed in the checkout (staged, unstaged, deletions) that `HEAD...<branch>` also changed. With none it prints `clear:` and exits 0. Otherwise it prints `dirty:`, the files and the fix (commit them, or wait until they are committed and rerun the merge line), exits 3, and runs no merge. A merge line puts it in front of the merge with `&&`. The tests share a new `LaneRepoCase` base with the receipt tests.

## Evidence

- judgment: three lane merge lines in one night stopped on "local changes would be overwritten" because another session had a staged deletion or a skill cut in the main checkout.

## Result

The three `DirtyCheckTest` tests fail against the script before the change (unknown verb, exit 2) and pass after. The staged deletion and the dirty page are both named, HEAD is unchanged and no MERGE_HEAD exists.

## Watch

Whether the next orchestration merge line that meets another session's changes prints the fix instead of failing mid-merge. Orchestration rules do not call the verb yet.

## Back-out

Remove the `dirty` verb, `dirty_check`, `dirty_merge_paths`, `EXIT_DIRTY` and the docstring paragraph; the test base class can stay.
