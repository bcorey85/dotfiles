---
type: "Change"
change_type: "fixed"
title: "verify-prep runs on a plan.md folder with no ticket"
description: "A ticketless /code plan folder (plan.md plus acceptance-criteria.md) now runs /verify-branch in plan-only mode with criteria owner plan; a ticketless folder missing either file exits 2."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T22:58:14-06:00"}
seq: 12
kind: "fix"
components: ["script/verify-prep", "script/verify-log", "script/verify-common", "script/plan-format", "agent/plan-verifier", "skill/verify-branch", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PlanOnlyTest::test_the_plan_md_path_resolves_to_its_folder_with_no_ticket"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify-prep`: a `plan.md` or `spec.md` path resolves to its folder, and the dir-mode plan is `spec.md`, else
`plan.md`, else the single `*-05-plan.md`. A folder with no ticket but with `plan.md` and `acceptance-criteria.md`
runs a new `plan-only` mode: ticket none, criteria from the folder, criteria owner `plan`. A ticketless folder that
lacks either file exits 2 and names both. `review/verify-log` and `review/verify_common.py` handle a run with no
ticket. `lib/plan_format.py` `plan_criteria_owner` gives `plan` for a ticketless `plan.md` whose folder holds
`acceptance-criteria.md` and whose `plan.md` exists (`plan_author_criteria_missing`). The plan-verifier, the
verify-branch and code skills read "the ticket's own words, or with no ticket the user's own request, stay met" so
they fit a run with no ticket; `review_fix.py` keeps the old wording until agent-evals-5e merges.

## Evidence

judgment: a session could not run /verify-branch on a ticketless plan.md folder (the path exited 4, the folder exited
2), and once a ticket file was written it ran `plan: none` and sent the user rulings on criteria the plan author wrote.

## Result

`PlanOnlyTest` in `test_verify_branch_script.py` and the owner tests in `test_plan_format.py` fail on the old tree and
pass; the plan_format, verify-branch and review-fix test files pass (578 tests).

## Watch

None: a resolver path with a fixed outcome.

## Back-out

Revert the commit.
