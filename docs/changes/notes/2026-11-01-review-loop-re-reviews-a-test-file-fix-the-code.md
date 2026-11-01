---
type: "Change"
change_type: "fixed"
title: "review loop re-reviews a test-file fix the code reviewer owned"
description: "Round two of the review loop sends a fixed test file back to the code reviewer that owned it in round one when no test reviewer read it, so a test-file fix is re-reviewed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:56:52-06:00"}
seq: 430
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_to_a_test_file_the_code_reviewer_owned_gets_a_second_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_round` keeps each dispatch's owned files in `round_fix`, as `(agent, owned, fixes)`.
- `second_round_plan` gives a reviewer the changed files of its kind, as before, plus a test file it owned in round
  one that no round-one test reviewer owned (`owns_in_round_two`).

## Evidence

judgment: a bug hunt on master 22c42b39 found that a code reviewer's fix to a test file, on a change too small for
a test reviewer, got no second review: round two gave the code reviewer source files only, so the fixed test file
had no reviewer and the loop ended converged.

## Result

The named test fails before (one code-reviewer call) and passes after (two). `test_review_loop_script` and
`test_change_size_bar`: 207 tests, 0 failed; ruff clean.

## Watch

None. The second review shows as a second code-reviewer call in the loop's output.

## Back-out

Revert `round_fix` to `(agent, fixes)`, drop `owns_in_round_two`, restore the test-path rule in
`second_round_plan`, and remove the test.
