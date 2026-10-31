---
type: "Change"
change_type: "fixed"
title: "a coder's PLAN-IMPACT that blames the toolkit stops the run instead of rewriting the plan"
description: "A coder's PLAN-IMPACT block now carries `cause: plan | toolkit`; a toolkit cause stops /code for the main session and dispatches no plan rewrite, and an unknown cause stops with a parse error."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:05:49-05:00"}
seq: 303
kind: "fix"
components: ["script/code-step", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_plan_impact_with_a_toolkit_cause_stops_and_dispatches_no_plan_rewrite"
asked: ""
proof: []
unmeasured: ""
---

## Change

- coder-core's PLAN-IMPACT block gets a `cause:` key. `toolkit` means a toolkit gate, hook or script is wrong and
  nothing in the plan is. Every other case is `plan`.
- `plan_format.plan_impact_cause` reads only that key. A reviewer-written block with no `cause:` key reads as `plan`.
  A block with no `cause:` key stops as unparsed, the same stop an unknown value gets, for a coder's own hand-back (the /code coder, or a review-loop fix coder). The review-loop script
  one-lines the block, so it sends the cause as the packet field `plan_impact_cause`, read before the block is
  one-lined; a reviewer agent's multi-line block is read for its `cause:` line instead.
- `review_coder_report` stops on a `toolkit` cause the way it stops on a coder blocker: the main session sees the
  block, and the coder can be resumed. No plan-change question and no plan-edit coder run. A cause that is neither
  value stops with a parse error that names both values. The rule lives in `plan_format.plan_impact_stop_cause` and
  `plan_format.cause_stop`, which the review-loop plan-impact route calls too. There the packet's
  `plan_impact_cause` comes from `plan_format.stopping_plan_impact_cause`: a review-loop fix coder's readable block with
  no `cause:` key stops as unparsed (`NO_CAUSE_LINE`), and a toolkit or unknown cause stops. A reviewer ask's block with
  no `cause:` key reads as `plan`, and so does a report with no readable block. The stop marks the block as handled, so a resumed coder's next hand-back is not stopped on it again. A toolkit
  cause on a report that changed no file takes the same stop, not the no-change stop.

## Evidence

judgment: on a work repo a coder's PLAN-IMPACT said nothing in the plan was wrong and the gate's base commit was. /code
still sent it down the plan-change route and dispatched a plan rewrite.

## Result

The named test fails before (the block went to the plan-edit coder) and passes after.
`test_a_plan_impact_with_an_unknown_cause_stops_and_names_both_causes` and
`test_a_plan_impact_with_a_plan_cause_is_adopted_as_before` cover the other values.

## Watch

None.

## Back-out

Remove the `cause:` line and its paragraph from coder-core's PLAN-IMPACT section, `PLAN_IMPACT_CAUSE`,
`PLAN_IMPACT_CAUSES`, `plan_impact_cause`, `plan_impact_stop_cause`, `stopping_plan_impact_cause`, `block_must_name_cause`, `NO_CAUSE_LINE` and `cause_stop` from `plan_format.py` (and `cause`
from `PLAN_IMPACT_KEY` in `code_step_report.py`), the `plan_impact_cause` packet field, the cause stops in `review_coder_report` and in the review-loop plan-impact route, and the tests.
