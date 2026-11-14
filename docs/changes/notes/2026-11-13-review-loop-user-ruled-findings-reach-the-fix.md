---
type: "Change"
change_type: "fixed"
title: "Review loop: user-ruled findings reach the fix coder marked, and a ruled plan impact is not held again"
description: "A fix run launched with --user-ruled passes the accepted findings and the ruling time to the loop, the fix coder sees each one marked as accepted by the user, and a plan impact on a criterion the user ruled is not held again from the coder or the reviewer route."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T13:00:25-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop", "script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_reviewer_plan_impact_on_a_ruled_criterion_goes_to_the_coder_not_the_asks"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_launch.py` writes `user-ruled:` and `user-ruled-at:` header lines; `review_loop_prompt_file.py` reads
them and stops when the time line is missing. `fix_first` marks each user-ruled issue `[accepted by the user, ruled
<time>]` in the coder prompt. One predicate, `ruled_plan_impact` in `review/review_loop_findings.py`, settles a plan impact by near title of a ruling text or of a finding the
user accepted, or by the same acceptance-criteria ids (`lib/plan_format.py`) named by a ruling: the carried
`plan impact: PLAN-IMPACT: ... acceptance_criteria: ACn` line that `present_plan_impacts` adds to `carried_findings`,
or the ruled PLAN-IMPACT block. A `decide` RESOLVED line holds no `acceptance_criteria:` line, so it gives no ids. A finding the user accepted settles by near title only: its criterion id names its subject, and it may
ask for another change to it. Both `route_plan_items` and `record_coder_plan_impact` use it. A plan-drift ask is
different: `repeats_an_ask` drops one on a criterion an accepted plan-change finding names, since the user already ruled on that
criterion and the reviewer asking about it again is the re-ask. The `user-ruled-at:` time
is `plan_format.ruled_at_now()`, the form a plan-deviation entry takes (`YYYY-MM-DD HH:MM`, local time).

## Evidence

judgment: after the user accepted and adopted an AC2 reword, the fix run only recorded the ruling in its launch file.
The fix coder read the finding's "needs the user" text, skipped it, and re-reported the plan impact; the loop held it
and the skip came back as an ask, so the user was asked again on two runs.

## Result

The new tests fail against master's scripts and pass; `test_review_loop_script.py`, `test_review_loop_findings.py` and
`test_review_loop_prompt_file.py` pass.

## Watch

None: a routing fix with a fixed outcome.

## Back-out

Revert the commit.
