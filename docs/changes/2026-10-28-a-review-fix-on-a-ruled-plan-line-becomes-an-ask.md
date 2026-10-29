---
type: "Change"
change_type: "fixed"
title: "A review fix on a plan line a recorded ruling covers becomes an ask"
description: "The scripted review loop reads the plan's Plan Deviations and Constraints sections and turns a fix finding on a ruled plan line into an ask instead of sending it to the coder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T12:00:00-05:00"}
seq: 194
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_on_a_plan_line_a_ruling_covers_becomes_an_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_findings.py` `ruled_plan_split`: a fix finding whose file:line is the run's plan file is ruled when the
  line sits under `## Plan Deviations` or `## Constraints`, or holds a backticked value a line there holds. A ruled
  fix becomes an ask with the note "a recorded plan ruling covers this line; the fix would undo it".
- `review_loop_script.py`: `LoopRun` takes the plan path from the prompt header; `review_round` runs the split before
  it files the round's findings. Every other plan-file fix still goes to the coder.

## Evidence

- Queue item review-reverts-a-plan-edit-an-orchestrator-ruled: a ruled Automated Verification value
  (`CARGO_BUILD_JOBS=4`, recorded in Constraints) was flagged as drift and the review fix put the old value back.
- The ruled-line test fails without the change (the coder runs the fix); the unruled-line test pins that other plan
  fixes still auto-fix.

## Result

- A recorded ruling reaches the session as an ask, and no review fix reverts it.

## Watch

—

## Back-out

Revert the commit.
