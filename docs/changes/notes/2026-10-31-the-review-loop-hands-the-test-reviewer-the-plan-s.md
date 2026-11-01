---
type: "Change"
change_type: "fixed"
title: "The review loop hands the test reviewer the plan's test strategy section"
description: "The test reviewer now reads the plan's plan-wide test rules on every phase, by script, instead of only when its own grep happens to hit them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T19:59:17-05:00"}
seq: 407
kind: "fix"
components: ["script/review-loop-script", "script/plan-format", "script/code"]
evidence: ["bench read", "tests"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_only_the_test_reviewer_gets_the_plans_test_strategy_section"
asked: ""
proof: []
unmeasured: ""
---

## Change

When the loop's header names a plan on disk, the loop reads its `## Testing Strategy` (or `## Test Strategy`) section with `plan_format.test_strategy_section`. It puts that section into the test reviewer's prompt only, beside the plan and phase lines, with the instruction to file a fix for each changed source that lacks the tests the section asks for. The code and smell reviewers get no new text. A plan with no such section changes nothing. `coder_packet.py` now finds the same section through `plan_format.test_strategy_range`, so the coder and the test reviewer read one range: a heading in a fenced block or before the first phase does not count, and any heading level from `##` to `###` matches.

## Evidence

On the code-phase bench, the plan-wide rule "each check constraint has a direct-insert test" sits at the end of a 2,500-line plan. It reached the test reviewer only when the reviewer's grep used the word constraint. One counted run never got the gap flagged and ended with 5 of 44 constraints tested; every other run reached 24 or more. Runs in both arms missed it in round one, and a later round or a restart caught it in most.

## Result

The new test fails before the change and passes after it. The review-loop test files (301 tests), `test_plan_format.py` (111) and `test_coder_packet.py` (19) pass. Lint and the duplicate-code check are clean.

## Watch

None: no intake number counts which rule a test reviewer read. A recurrence shows as test-reviewer escapes in `review-escapes.jsonl`.

## Back-out

Revert the commit.
