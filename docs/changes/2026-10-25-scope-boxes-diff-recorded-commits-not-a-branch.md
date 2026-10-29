---
type: "Change"
change_type: "fixed"
title: "Scope boxes diff recorded commits, not a branch name"
description: "plan check now fails a plan box that diffs main...HEAD, and the closing-phase text names the form that survives merge and fails when empty. Before, such a box read nothing once the branch merged, so a box ticked after merge passed with nothing checked."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:35:30-05:00"}
seq: 33
kind: "fix"
components: ["script/code-step", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_plan_check_fails_a_box_that_diffs_a_moving_branch_name"
asked: ""
proof: []
unmeasured: "The box is caught at write time, so it leaves no later row; the intake has no count of boxes that diffed a branch name."
---

## Change

- `lib/plan_format.py`: `moving_base_diff` matches a `git diff` span that starts at main, master, develop or trunk (with or without `origin/`).
- `code/code_step_boundary.py`: `verification_format_failure` reports such a box in any open phase, closing phases included (every checkbox line of a closing phase is read), with the fix text.
- `skills/_shared/closing-phases.md`: a scope box diffs two recorded commit ids and fails on an empty diff: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"`.

## Evidence

judgment: a peer reported the Scope-verified box in three plans using `git diff main...HEAD`; after merge that diff is empty for any branch, so ticking the box passes with nothing read.

## Result

Installed in the fix/eng-spec-ac-and-scope branch; takes effect when merged.

## Watch

None.

## Back-out

Remove the `moving_base_diff` branch from `verification_format_failure` and the closing-phases paragraph.
