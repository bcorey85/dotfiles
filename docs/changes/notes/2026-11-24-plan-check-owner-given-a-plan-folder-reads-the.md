---
type: "Change"
change_type: "fixed"
title: "plan_check owner given a plan folder reads the ticket inside it"
description: "A lane that passes a plan folder to plan_check owner now gets the criteria owner of the ticket inside it, so it stops sending a session-owned criterion to the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T23:20:12-06:00"}
seq: 7
kind: "fix"
components: ["script/plan-check"]
evidence: ["defect report"]
watches: []
test: "tests/scripts/test_plan_check.py::test_owner_given_the_plan_folder_reads_the_ticket_inside_it"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`plan_criteria_owner` reads the ticket inside a folder argument first, even before a plan file exists. Only a
folder with no ticket resolves the plan file inside it (`spec.md`, `plan.md`, else one `*-05-plan.md`); a folder
with neither a ticket nor a plan file exits 1 and names those forms, where it printed owner `user` before. The folder lookup moved from `verify-prep` into `lib/plan_format.py`, so both read one
resolver.

## Evidence

A lane ran `plan_check.py owner docs/plans/<slug>` and got `user` for a session-sourced ticket, then put a
narrowing question to its orchestrator as a user ruling.

## Result

The folder test failed before (`'user' != 'session'`) and passes after; the no-plan-file test failed before
(`0 != 1`) and passes after; the ticket-and-no-plan-file test failed before (exit 1, "no plan file") and passes
after, printing `session`. test_plan_check, test_plan_format and the two verify-prep test files: 239 tests, 0 failed.

## Watch

None: a fix with a failing-then-passing test.

## Back-out

Revert the branch commit; `verify-prep` keeps its own folder lookup again.
