---
type: "Change"
change_type: "fixed"
title: "the removed-change guard counts moved and edited lines as kept"
description: "The review loop's fix-removed-change guard subtracts the removed lines the fix passes wrote again as near copies, so a block moved and edited on the way no longer stops the loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T16:26:52-06:00"}
seq: 6
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_change_removal.py::ChangeUnderReviewTest::test_a_block_a_fix_pass_moves_and_edits_on_the_way_is_not_gutted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/change_removal.py`: `is_gutted` and `removal_blocker` take `written`, and the guard fires on removed less written.
The blocker names the written count. `review/review_loop_plan.py`: `ChangeUnderReview.removal()` returns the removed
map and the count of removed lines the fix passes wrote again as near copies (`change_removal.rewritten_count`, difflib
ratio 0.8, each line matched once); a line moved unchanged, a rename included, is not new. Only lines at or above
ratio 0.8 count; same-style unrelated code does not reach it. The count runs only once the raw removal reaches the gutted threshold.
`review/review_loop_script.py` passes `written` through.

## Evidence

judgment: a /code fix pass moved lines within a file and edited them, and the loop stopped with `fix-removed-change`.

## Result

The moved-and-edited and moved-unchanged tests fail on the old tree and pass; `test_change_removal.py` (40) and
`test_review_loop_script.py` (294) pass, the rename-and-revert stop test among them.

## Watch

None: a counting rule with a fixed outcome.

## Back-out

Revert the commit.
