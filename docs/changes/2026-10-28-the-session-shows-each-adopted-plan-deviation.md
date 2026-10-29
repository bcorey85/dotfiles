---
type: "Change"
title: "The session shows each adopted plan deviation, and a later review drops a stale one"
description: "A plan impact adopted below the acceptance criteria prints one deviation line, with no question: in code_step's say.md at phase end and run end, and in the /review and /fix closing block. Adopted deviations carry into a re-dispatch only when the dispatch prompt holds the resolved plan_impact; any other review shows none."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:39:30-05:00"}
seq: 224
kind: "user-rule"
components: ["script/review-fix", "script/handback", "script/code-step", "script/plan-format", "skill/fix", "skill/review", "agent/code-reviewer", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_phase_end_block_lists_the_deviation_adopted_in_the_phase"
asked: "2026-10-28: can the main agent summarize plan deviations instead of burning a round to confirm? then at least i can still monitor for drift"
proof: []
unmeasured: ""
---

## Change

- `plan_format`: `below_criteria_ruling` appends the disagreement summary to `BELOW_CRITERIA_RULING`; `below_criteria_deviations` lists a plan's adopted deviations, by phase.
- `code_step_boundary`: the phase-end hand-back lists the phase's adopted deviations. The run-end hand-back lists every phase's, headed "this plan".
- `review_fix.present_plan_impact`: a block that changes no acceptance criterion prints `ACTION: redispatch` with "Show the user this line, and ask nothing: Plan deviation adopted, no question asked: ...". The closing block of the re-dispatched run lists the adopted deviations.
- `handback`: a dispatch row records `resolved_plan_impact` when its prompt carries `plan_impact: RESOLVED`. `review_fix.new_state` carries adopted deviations only into such a dispatch; any other review drops them.
- `/fix` and `/review`: the `redispatch` action shows the deviation line and asks nothing.
- opencode `code-reviewer` and `review-loop` ports gain the `acceptance_criteria:` line and the carried findings.

## Evidence

- The user's words, quoted in `asked`.

## Result

- New tests: the phase-end and run-end deviation tests (test_code_step), the deviation shown and carried and the unrelated review after an abandoned re-dispatch (test_review_fix_script), `BelowCriteriaDeviationTest` (test_plan_format).

## Watch

—

## Back-out

Revert the commit. Adopted deviations then go unshown.
