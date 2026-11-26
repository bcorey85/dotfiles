---
type: "Change"
change_type: "fixed"
title: "review loop puts back text an acceptance criterion quotes and files an ask"
description: "A review-loop fix pass that removes or rewords text an acceptance criterion quotes has those lines put back, keeps its other edits, and files one ask naming the criterion, the file and the text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T02:54:23-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_criteria_quotes.py::CriteriaQuoteLoopTest::test_loop_puts_back_the_ac_quoted_line_and_keeps_the_fix"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Before each fix pass the loop reads the spans the plan's acceptance criteria and its ticket quote, and notes the
files in scope that hold one. After the pass, a lost span's lines go back in place, the pass's other edits stay, and
one ask per span names the criterion, the file and the text. An accepted ask lets the change stand; a rejected one
keeps the put-back with no new ask. A malformed criteria file turns the guard off for the run with a `tool_fault`
note naming the file.

Q1: with no plan on disk the guard does not run; criterion text in the brief alone is not read.

## Evidence

Judgment from the queued incident: a fix pass reworded a line an acceptance criterion quoted, and the loop kept it.

## Result

`CriteriaQuoteLoopTest` passes (28 tests in the file): the loop test ends with the quoted line restored, the other fix kept, and one ask naming the criterion; the accepted, rejected, no-plan and malformed-criteria loop tests pass too.

## Watch

None: a test pins it.

## Back-out

`git revert` the commits.
