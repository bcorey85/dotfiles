---
type: "Change"
change_type: "fixed"
title: "Code review start prints the defer action for held plan impacts"
description: "code_review_start.py prints an ACTION: defer-plan-impacts line after a packet that holds unruled plan impacts, so /code stops reporting a converged review the commit gate still counts as dirty."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 2
kind: "fix"
components: ["script/code-review-start"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_converged_packet_with_a_held_plan_impact_prints_the_defer_action"
asked: ""
proof: []
unmeasured: ""
---

## Change

After the packet prints, `held_impact_lines` reads it with `handback.load` and `handback.held_plan_impacts`. With any held impact it prints one `ACTION: defer-plan-impacts` line: the count, the handoff's `plan_impact` line to set (`review_fix.DEFER_LINE`) and `DEFER_COMMAND <handoff>`. A packet that does not parse prints that its held impacts are unknown.

## Evidence

judgment: a /code run reported a converged review with an unruled plan impact; the commit gate then refused the commit. The new test fails on the base commit and passes after.

## Result

`test_code_review_start.py` 17 of 17 pass; lint clean.

## Watch

—

## Back-out

Remove `held_impact_lines`, its call in `main`, `DEFER_COMMAND` and its allow entry in `test_toolkit_self_location.py`, and the two new tests.
