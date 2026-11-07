---
type: "Change"
change_type: "fixed"
title: "fix-removed-change counts a line the fix pass re-adds as kept"
description: "The review loop's fix-removed-change check counts a line the fix pass adds to any file as kept, even a file that held the same line at HEAD, so a fix that moves added code into a helper no longer stops the loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T00:36:40-06:00"}
seq: 1
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_change_removal.py::ChangeUnderReviewTest::test_a_block_a_fix_pass_moves_back_into_the_file_it_left_is_not_removed"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/change_removal.py` counts an added line as kept when the fix pass adds it to any file, across files and across a commit made during the loop. `review/review_loop_plan.py` passes the file set after a mid-loop commit. Lines the fix deleted without adding them elsewhere still count as removed.

## Evidence

judgment: an agent-evals /code run stopped on fix-removed-change twice after its fix pass moved a helper into a new module; the moved lines were counted as removed, and the commit gate then blocked a correct change. The new tests fail before the change and pass after.

## Result

`test_change_removal.py` passes; full suite 3230 tests, 0 failures.

## Watch

—

## Back-out

Revert the cross-file kept-line count in `lib/change_removal.py`, the file-set change in `review/review_loop_plan.py`, and the new tests.
