---
type: "Change"
change_type: "fixed"
title: "Review loop merges a re-raised finding and its ask"
description: "A run records one finding and one ask when a later round raises the same file, line and class again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T21:11:33-06:00"}
seq: 7
kind: "fix"
components: ["shared/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_repeats.py::RepeatedFindingTest::test_a_fix_raised_again_on_the_same_file_line_and_class_is_fixed_once"
asked: ""
proof: []
unmeasured: "A fixture test pins it; the work logs hold no count of repeat findings per run."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change
The review loop keys a finding by its file, exact line and class. A later round that raises the same key again adds nothing to the fixed list and files no second ask, so a capped run shows its real count and the user answers one question.

## Evidence
A capped run listed 29 fixed findings, about six of them a re-raise of an earlier one, and held one ask under two finding ids.

## Result
Two fixture tests failed before the change (fixed list and ask list each held the repeat twice) and pass after it. A test of two different lines stays two.

## Watch
None: no intake number reads it.

## Back-out
Revert the commit.

