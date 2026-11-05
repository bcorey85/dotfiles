---
type: "Change"
change_type: "fixed"
title: "An ask tagged PLAN-IMPACT none no longer counts as a plan change"
description: "plan_format.PLAN_CHANGE_MARK skips a PLAN-IMPACT tag whose value is none or no, so the review loop stops holding a plan impact on an ask that changes no plan."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 5
kind: "fix"
components: ["script/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::PlanChangeMarkTest::test_an_ask_tagged_plan_impact_none_is_not_marked"
asked: ""
proof: []
unmeasured: ""
---

## Change

`PLAN_CHANGE_MARK` gains a negative lookahead for `: none`, `: no` and `: no.`, through bold and backtick marks, multiline and case-blind. A value that only opens with the word "no" still marks.

## Evidence

judgment: an ask tagged `PLAN-IMPACT: none` held the review as a plan change. Real transcript shapes checked: `PLAN-IMPACT: none`, `none.`, `no`, `**PLAN-IMPACT:** none`, `none of substance`. Both new tests fail or hold as intended on the base commit and pass after.

## Result

`test_plan_format.py` 113, `test_review_loop_script.py` 222, `test_handback.py` 180, `test_review_fix_script.py` 170: all pass; lint clean.

## Watch

—

## Back-out

Remove the lookahead from `PLAN_CHANGE_MARK` and the two new tests.
