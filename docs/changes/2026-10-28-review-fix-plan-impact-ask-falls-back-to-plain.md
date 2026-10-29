---
type: "Change"
change_type: "fixed"
title: "review_fix plan-impact ask falls back to plain text when AskUserQuestion is missing"
description: "The plan-impact action told the session to call AskUserQuestion with no fallback when the tool is missing; it now says to ask in plain text with numbered options and decide on the answer."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T01:41:49-05:00"}
seq: 157
kind: "fix"
components: ["script/review-fix", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_plan_impact_prints_the_modal_and_decide_builds_the_redispatch_with_both_counters"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `present_plan_impact`: without AskUserQuestion, the session asks the same question in plain text with the options
  numbered, waits, and maps the reply to `adopt`, `keep` or `discuss`. For `adopt` or `keep` the user's words go in
  `--ruling`; for `discuss` the session runs `decide discuss`. The `decide` step already takes `--by user --ruling`,
  so it is unchanged.
- The `ask-user-plan-impact` line in the review and fix skills names the same fallback.
- Closes the queue item review-fix-plan-impact-action-calls.

## Evidence

- A session without AskUserQuestion got an action it could not run.
- The fallback-text assertion fails before the change.

## Result

- The review_fix, review_fixes and handback tests pass, and ruff check is clean.

## Watch

—

## Back-out

Revert the commit. The plan-impact action names only AskUserQuestion again.
