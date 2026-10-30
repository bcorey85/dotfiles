---
type: "Change"
change_type: "changed"
title: "Code-step reads the plan phase text through one helper"
description: "One phase-text reader, one missing-plan stop and one phase-entry stop replace the copies in the code-step scripts, with no change in what a run prints or saves."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T19:04:51-05:00"}
seq: 288
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_tick_refuses_an_unknown_phase_a_done_phase_and_a_missing_state"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step_core.current_phase_text(repo_dir, plan_rel, phase)` replaces six reads of a plan phase's text in
code_step_core, code_step_boundary, code_step_review and code_step. It takes the plan path and phase, not the
state, because the tick check reads the phase the user named. It raises `OSError` for an unreadable plan and
returns None for a phase that is gone, so `stale_phase_reason` still tells the two apart. `MISSING_PLAN_STOP`
replaces three copies of the missing-plan stop. `plan_format.phase_entry_stop(entries, phase_id, plan_name,
done_tail, unlisted_tail)` replaces `code_step_start.named_phase_stop` and `code_step_boundary.tick_entry_stop`;
the two tails keep each verb's closing words.

## Evidence

A read-only simplify review found the copies.

## Result

The tests that pin each stop's wording pass unchanged. The full suite passes.

## Watch

None; a refactor with no behavior change has no intake number.

## Back-out

Revert the commit: the copies come back with the same wording.
