---
type: "Change"
title: "A finding the coder made no change for is not listed as fixed"
description: "When a coder pass, full-check repair or class-closure pass changes no file, its findings go to skipped_fp with the reason the coder made no change, not to fixed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 192
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_the_coder_made_no_change_for_is_skipped_not_listed_as_fixed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_script.py`: `fix_round` with no changed file moves each unskipped finding to `skipped_fp` with "the
  coder made no change", and round two re-reviews its file. `mark_repaired` does the same for the full-check and
  class-closure coders.

## Evidence

- Queue item code-review-lists-findings-on-files-absent-from: the hand-back listed findings under Fixed with no diff
  behind them.
- The new test fails on the old script: the finding lands in `fixed`.

## Result

- Every finding under Fixed has a change behind it.

## Watch

—

## Back-out

Revert the commit.
