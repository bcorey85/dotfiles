---
type: "Change"
change_type: "fixed"
title: "Test reviewers get the plan's Testing Strategy section in their prompt"
description: "A plan-wide test rule reaches every reviewer that owns a test file, not only one whose grep happens to hit the line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T19:46:58-05:00"}
seq: 406
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_the_test_reviewer_prompt_carries_the_plans_testing_strategy_and_the_code_reviewer_does_not"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `plan_format.py`: `testing_strategy_span` finds the plan's `## Testing Strategy` section, which ends at the next
  `---` rule or level-2 heading outside a code fence; `testing_strategy_body` returns its lines, or nothing. The
  coder packet reads its Testing Strategy line range from the same span, so a `###` subsection inside the section no
  longer cuts the range short.
- `review_loop_script.py`: the loop reads the section once when the plan is on disk, and `review_one` passes it to
  the reviewer prompt.
- `review_loop_prompts.py`: a reviewer that owns any test file gets the section under "The plan's Testing Strategy
  section (applies to every phase):". A reviewer with no test files, a run with no plan on disk, and a plan with no
  such section add nothing.

## Evidence

judgment: on the code-phase bench, a plan-wide rule at the end of a 2,500-line plan (each check constraint has a
direct-insert test) reached the test reviewer only when its grep used the word constraint. One run never had the gap
flagged and ended with 5 of 44 constraints tested, against 24 or more in the other runs.

## Result

The named test fails before (the test reviewer's prompt has no section line) and passes after. A second test pins
that a plan with no section adds nothing, and `test_plan_format.py` pins the span's ends. The review loop, plan format
and coder packet test files: 302 tests, 0 failed.

## Watch

None.

## Back-out

Revert `testing_strategy_span`, `testing_strategy_body`, the coder packet's use of the span and the
`testing_strategy` argument of `reviewer_prompt`, and drop the new tests.
