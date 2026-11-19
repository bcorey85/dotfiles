---
type: "Change"
change_type: "fixed"
title: "Accepted asks drop the question and the Change if label from their change text"
description: "An ask written as `Change if not accepted:`, `Change if yes:` and the other `Change if <condition>:` forms now splits its question from its change, and an ask with two such branches is refused as conditional."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-19T00:56:36-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop-findings", "script/review-asks"]
evidence: ["tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_accepted_ask_whose_change_follows_a_change_if_not_accepted_mark_carries_only_the_change"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_accepted_ask_whose_change_follows_a_change_if_not_accepted_mark_carries_only_the_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

The ask change marker reads `Change if <up to three words>:` with optional markup, not only `change:` and `change if accepted:`. An ask with two or more `Change if <answer>:` marks splits at the first of them; an ask whose question ends in `?` followed by a plain `change:` and a later conditional mark splits at the plain mark (`opens_with_plain_mark_then_condition`); otherwise it splits at the last mark. So its change keeps every branch, and `CONDITIONAL_CHANGE` names a `Change if <answer>:` label inside a change as conditional.

## Evidence

tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_accepted_ask_whose_change_follows_a_change_if_not_accepted_mark_carries_only_the_change

## Result

An accepted ask's findings-file line holds only the change, with no question and no declined branch. A two-branch ask is refused by asks-done until the ruler answers `modified:<change>`.

## Watch

—

## Back-out

Revert the `ASK_CHANGE_MARK` pattern, the first-mark split and the `opens_with_plain_mark_then_condition` split in `ask_parts`, and the added `CONDITIONAL_CHANGE` alternative.
