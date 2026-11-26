---
type: "Change"
change_type: "changed"
title: "Test-reviewer reads unrun tests by hand"
description: "When a repo's full suite runs only in CI, the review loop adds a by-hand pass to the test-reviewer's prompt: equality asserts with mismatched types, state shared across subtests or test methods, and expected values the setup never makes true. The agent file does not grow."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:25:54-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-prompts", "agent/test-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_prompts_unrun_tests.py::UnrunTestsRuleTest::test_the_test_reviewer_of_a_ci_only_repo_gets_the_unrun_tests_rule"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `claude/.claude/scripts/review/review_loop_prompts.py`: a `UNRUN_TESTS_RULE` constant. `reviewer_prompt` appends it
  to the test-reviewer's prompt when `full_check.full_suite_runs_in_ci(repo)` is true. Other reviewers and repos with
  a local quality check get no new line. `claude/.claude/agents/test-reviewer.md` is unchanged.
- Test: `tests/scripts/test_review_loop_prompts_unrun_tests.py`.
- agent-evals `02c51437`: a `rule_in_prompt` scenario mode in `bin/rule_meter.py` (the on arm appends the rule to the
  task prompt; toolkit files stay whole in both arms), scenario UT01, a django plant with a str-against-UUID assert
  and an entry shared across subtests, and the `flags_unrun_test_faults` detector.

## Evidence

- Queue item `test-reviewer-does-not-read-new-tests-closely-when`: in a repo whose suite runs only in CI, the
  test-reviewer passed new tests that failed in CI on a str-against-UUID assert and a fixture shared across subtests.

## Result

- Rule meter UT01, 4 runs per cell, sonnet: supportive on 4/4, off 4/4; neutral on 4/4, off 4/4; competing on 4/4,
  off 3/4. Total on 12/12 (100%), off 11/12 (92%).
- The on arm flags both seeded faults in every run, which meets the queue item's eval clause. The off arm almost
  always does too, so on this small plant the line shows no clear gain. It stays: it costs nothing outside CI-only
  repos, and the queue item's miss came on a large diff.
- The on-arm runs used an earlier opening sentence ("The tests never ran locally."); review reworded it to "The full
  suite runs only in CI, so a new test may never have run locally." The three checks are word for word the same.

## Watch

—

## Back-out

Revert the lane's commit in dotfiles and agent-evals `02c51437`.
