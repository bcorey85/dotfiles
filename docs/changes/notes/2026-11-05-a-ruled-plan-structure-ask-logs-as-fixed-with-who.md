---
type: "Change"
change_type: "fixed"
title: "a ruled plan-structure ask logs as fixed with who ruled"
description: "refactor_flow.py log accepts ruled_by (user or session) on an ask finding, lets a ruled plan-structure ask log as actioned=fixed, and sends ask_decided_by on its finding row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:40:23-06:00"}
seq: 10
kind: "fix"
components: ["skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_log_writes_a_ruled_plan_structure_finding_as_fixed_with_who_ruled"
asked: ""
proof: []
unmeasured: ""
---

## Change

A finding may carry `ruled_by` (`user` or `session`), on `disposition=ask` rows only. A `plan_structure: true` finding with `ruled_by` may log `actioned=fixed`; without it the refusal stands. The finding row carries `ask_decided_by=<ruled_by>`. `skills/refactor/SKILL.md` names the field.

## Evidence

judgment: in a repo whose CLAUDE.md hands design rulings to the session, the session ruled a plan-structure ask and the coder applied it, but `log` forced it to be logged as an open ask, so the ledger showed a ruled, done ask as open. The new test fails on f22db22c and passes after.

## Result

`test_refactor_flow.py` passes; full suite 3199 tests, 0 failures.

## Watch

—

## Back-out

Revert the `ruled_by` validation and row field in `refactor_flow.py`, the SKILL.md line, and the tests.
