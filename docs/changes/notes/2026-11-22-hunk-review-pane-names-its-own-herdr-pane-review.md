---
type: "Change"
change_type: "fixed"
title: "hunk-review-pane names its own herdr pane review"
description: "A review pane started by hand now labels itself review, so nvim-jump finds it and opens nvim on a jump without a manual pane rename."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T15:48:48-06:00"}
seq: 34
kind: "fix"
components: ["script/hunk-review-pane", "script/nvim-jump"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_hunk_review_pane.py::HunkReviewPaneRenameTest::test_unlabeled_pane_renames_itself_review"
asked: ""
proof: []
unmeasured: "a one-line fix; no intake number reads it"
---

## Change

When `$HERDR_PANE_ID` is set, `hunk-review-pane` runs `herdr pane rename "$HERDR_PANE_ID" review` before it starts hunk. A failed rename is ignored. Outside herdr it makes no call.

## Evidence

judgment: the first live jump from a pane started with `hw` failed with "no review pane for its repo could open one" until the pane was renamed by hand; the old stubs always carried the label.

## Result

The new test fails without the rename line (no herdr call recorded) and passes with it; the unset and failing-herdr cases also pass.

## Watch

—

## Back-out

Remove the `herdr pane rename` line from `hunk-review-pane` and delete `tests/scripts/test_hunk_review_pane.py`.

