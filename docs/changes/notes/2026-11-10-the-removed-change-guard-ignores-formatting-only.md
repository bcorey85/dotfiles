---
type: "Change"
change_type: "fixed"
title: "The removed-change guard ignores formatting-only hunks"
description: "A hunk whose only change is whitespace, line breaks, quote style or a trailing comma before a closing bracket adds no lines to the change under review, so a fix pass that reverts formatter churn no longer stops the loop with fix-removed-change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:40:07-06:00"}
seq: 4
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_change_removal.py::FormattingOnlyHunkTest::test_reverting_twelve_reflowed_lines_is_not_gutted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/change_removal.py` `added_lines` diffs the two texts with `difflib.SequenceMatcher` and leaves out the lines of each `replace` hunk whose old and new blocks are equal once normalized (whitespace dropped, `'` read as `"`, a comma before `)]}` dropped). Each side's formatting-only lines are subtracted before the difference, so a reflowed line never cancels a copy the change really added. The normalizing helpers live in `lib/source_text.py`. A hunk with a real change counts its lines as before.

## Evidence

judgment: a /code run's review loop stopped with `ChangeRemovedError` after a fix pass reverted formatter churn on base lines; the reflowed lines had counted as the change's added work. The new `FormattingOnlyHunkTest` cases fail on the old code (6 failures) and pass after.

## Result

The loop's full check on the final tree passed: 3362 tests, 0 failed.

## Watch

—

## Back-out

Revert `added_lines` in `lib/change_removal.py`, the helpers in `lib/source_text.py`, and `FormattingOnlyHunkTest`.
