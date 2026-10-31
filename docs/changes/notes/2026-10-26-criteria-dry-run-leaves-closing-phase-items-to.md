---
type: "Change"
change_type: "fixed"
title: "Criteria dry-run leaves closing-phase items to their skill, as the plan check does"
description: "criteria_dry_run.py skips the Automated Verification items of closing phases (Refactor pass, Test audit, Verify pass, Recap), which their skill checks from the session's evidence and never runs, so it no longer reports them UNPARSED while the plan check passes them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T21:58:13-05:00"}
seq: 72
kind: "fix"
components: ["script/criteria-dry-run", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_dry_run.py::ClosingPhaseTest::test_a_closing_phase_item_is_left_to_its_skill_like_the_plan_check_leaves_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `criteria_in_plan` skips every phase whose title `plan_format.closing_skill` names. Its items get no check line and
  no number, so they no longer make the dry-run exit 1.
- The plan check (`verification_format_failure`) already skipped closing phases. Both tools now read a closing phase's
  items the same way: evidence the closing skill records, never a command to run.

## Evidence

- A planner's dry-run printed UNPARSED for two assignment-statement items (`VAR="$(...)" && test ...`) in the Refactor
  and Test audit phases while `code_step.py plan check` exited 0 on the same spec. /code never runs a closing phase's
  commands: `skill-done pass` writes the session's evidence under each item.
- The new test fails on the base commit (UNPARSED on the closing item) and passes after.

## Result

- The dry-run tests pass, and ruff passes on both changed files. The full suite passes: 2385 tests, 0 failed. The lint
  step fails on one E402 in `tests/scripts/test_code_step_commit_subject.py`, a staged file from other work that this
  change does not touch.

## Watch

—

## Back-out

Revert the commit.
