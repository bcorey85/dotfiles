---
type: "Change"
change_type: "fixed"
title: "asks-done's outcome error says a leave-it option takes rejected"
description: "When asks-done refuses an outcome word, its error now says what each outcome does: accepted applies the ask's proposed change, rejected leaves the code as it is (the outcome for a leave-it or accept-the-gap option), and modified:<change> applies another change. A fork that passed the option letter no longer falls back to accepted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:53:09-06:00"}
seq: 13
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_asks.py::ReadOutcomesTest::test_an_unknown_outcome_word_error_says_rejected_is_the_leave_it_outcome"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_fix_asks.py` `read_outcomes` builds its unknown-outcome error from the `review_asks` outcome constants
and their meanings, and the asks-done usage text in `review/review_fix.py` uses the same constants.

## Evidence

judgment: a resumed /review answered an ask with option c (leave the code as it is). asks-done refused the word, the
fork then logged `accepted`, and the store recorded a change the user had declined. The new test fails on the old
error text and passes after.

## Result

`bash tests/run.sh` passes on the branch.

## Watch

—

## Back-out

Revert the error text in `read_outcomes` and the usage text in `review_fix.py`.
