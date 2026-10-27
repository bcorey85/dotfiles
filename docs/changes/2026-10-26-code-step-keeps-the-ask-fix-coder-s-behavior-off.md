---
type: "Change"
title: "code_step keeps the ask-fix coder's behavior off the phase Implemented line"
description: "An ask-fix coder BEHAVIOR line shows as its own Ask-fix line in say.md, not on the phase Implemented line or Behavior delta."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T17:13:55-05:00"}
seq: 65
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest.test_an_ask_fix_coder_s_behavior_stays_off_the_phase_implemented_line"
asked: ""
proof: []
unmeasured: ""
---

## Change

The ask-fix coder's BEHAVIOR lines are kept in their own state list and printed as an Ask-fix line; the phase behavior list is unchanged.

## Evidence

judgment; the test fails before the edit and passes after.

## Result

say.md no longer contradicts itself about what the phase changed.

## Watch

—

## Back-out

Revert the code_step.py edit.

