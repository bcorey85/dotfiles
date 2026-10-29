---
type: "Change"
change_type: "fixed"
title: "code_step carries a plan-impact round's other asks and pending findings"
description: "After a plan-impact review round, its other asks and pending findings go to the user and into the next review handoff."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T17:13:55-05:00"}
seq: 64
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest.test_a_plan_impact_round_s_other_asks_and_pending_findings_reach_the_question_and_the_next_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

On a plan-impact review packet, code_step saves the other asks, remaining findings and closing prose, prints them under the question, and adds a carried-findings list to the next review handoff.

## Evidence

judgment; the test fails before the edit and passes after.

## Result

Test gaps left open by a plan-impact round no longer vanish after the ruling.

## Watch

—

## Back-out

Revert the code_step.py edit.

