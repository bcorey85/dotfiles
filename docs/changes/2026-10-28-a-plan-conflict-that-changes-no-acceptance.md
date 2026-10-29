---
type: "Change"
change_type: "changed"
title: "A plan conflict that changes no acceptance criterion is adopted without asking"
description: "A PLAN-IMPACT block now ends with an acceptance_criteria line. When every block says none, /review, /fix and /code adopt the plan change by rule, log it under Plan Deviations as the session's ruling, and re-dispatch with no question to the user. Any other value, or no line at all, still asks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T23:45:38-05:00"}
seq: 224
kind: "user-rule"
components: ["script/review-fix", "script/code-step", "script/plan-format", "skill/coder-core", "agent/code-reviewer", "agent/review-loop", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-28: plan drift asks are \"extraordinarily frustrating - the main agent stops and asks me to accept the changes constantly\" and \"its been happening forever\"; the user answered \"yes\" to: below the acceptance criteria the code wins, the change is logged in Plan Deviations, and only an acceptance-criterion change asks."
proof: []
unmeasured: ""
---

## Change

- `lib/plan_format.py` gains `changes_acceptance_criteria`: false only when each PLAN-IMPACT in the text says `acceptance_criteria: none`. A block with no such line counts as an AC change, so it still asks.
- `review_fix.py packet`: a plan-impact packet that changes no criterion prints `ACTION: redispatch` with a session ruling and the Plan Deviations lines, in place of `ask-user-plan-impact`. `decide` and the rule share `record_plan_ruling`.
- `code_step_review.py emit_plan_impact_modal`: the same test runs before the question. A no-AC impact goes straight to `decide adopt --by session`, which dispatches the plan-edit coder.
- `code_step_report.py` keeps the `acceptance_criteria:` line in the block it lifts from a coder report.
- coder-core, code-reviewer, reviewer-calibration and review-loop ask for the `acceptance_criteria:` line; coder-core says the code wins below the criteria. The review and fix skills route the new `redispatch` action.
- Closes queue item 328, below-the-acceptance-criteria-the-code-wins-plan.

## Evidence

- The user's ruling, quoted in `asked`.
- Failing first: on the base commit, the no-AC tests in `test_review_fix_script.py` and `test_code_step.py` fail; the tests that a named criterion still asks pass on both.

## Result

- The scoped suites pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Revert the commit.
