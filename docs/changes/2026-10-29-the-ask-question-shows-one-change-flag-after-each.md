---
type: "Change"
title: "The ask question shows one change flag after each modified outcome"
description: "The /code question for review asks spells out the asks-done layout, a --change right after each modified word, so the first answer parses."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T06:52:26-05:00"}
seq: 237
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_question_for_the_user_shows_one_change_flag_after_each_modified_word"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_review.py`: the question.md text for review asks says to put `--change "<text>"` right after each
  `modified` word, one per modified ask, and shows the layout
  `asks-done accepted modified --change "<text>" modified --change "<text>"`.

## Evidence

- The old text said "After a modified outcome, add --change". A main session sent four `modified` words and one
  trailing `--change`. asks-done refused it, because it needs one `--change` per modified ask, and the session spent
  a round trip on the retry.

## Result

- The new test fails before (no layout in the question) and passes after.

## Watch

—

## Back-out

Revert the commit.
