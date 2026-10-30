---
type: "Change"
change_type: "added"
title: "plan check accepts an Agent-run tag for checks an agent runs locally"
description: "A plan can tag a local check that an agent runs but the plan check must not, so it is no longer mislabeled Human-only and routed to the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T04:08:53-05:00"}
seq: 321
kind: "fix"
components: ["script/plan-format", "script/code-step", "script/verify-branch", "agent/plan-verifier"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::GateEnvTest::test_an_agent_run_item_is_tagged_in_any_case_with_or_without_a_bold_label"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `plan_format.py` reads a fourth Automated Verification tag, `**Agent-run**:` (or plain `Agent-run:`, any case). The
  plan check accepts it and neither it nor the phase close runs it. Its open box still needs evidence:
  `open_success_items` leaves out only N/A, CI-verified and human-only boxes.
- `/code`'s phase-close line names such an item as `not run here: agent-run, the session runs it - <text>`. The plan
  check's shape text and its no-command problem name the tag.
- The plan verifier is told via the `verify-prep` payload to run an Agent-run item as its text says and record its
  output, and never to mark it human-only.
- `verify-log` refuses a `done` row for an Agent-run item whose `evidence` is empty, exits 2 and writes nothing, so a
  `done` verifier row for it needs non-empty evidence.
- `plan-format.md` documents the tag.

## Evidence

judgment: a plan reviewer flagged a spec that tagged a real-data timing check `Human-only:` because the plan check
had no tag for a check that an agent runs locally but the checker must not run. That tag routes the check to the user.

## Result

The named test fails before (`deferred_verification_tag` returns None for every Agent-run form) and passes after.
`test_finish_phase_says_an_agent_run_item_is_left_to_the_session` in `test_code_step.py` and
`test_a_done_agent_run_row_with_no_output_exits_2_names_the_item_and_writes_nothing` in
`test_verify_branch_script.py` also fail before and pass after.

## Watch

None.

## Back-out

In `plan_format.py`, delete `AGENT_RUN_TAG` and `NO_EVIDENCE_TAGS`, drop `agent-run` from `DEFERRED_VERIFICATION` and
`DEFERRED_TAG_NAMES`, restore the `runs_no_command` skip in `open_success_items`. Also drop `not_run_label` in
`code_step_boundary.py`, the Agent-run words in `code_step_verification.py`, `verify-prep` and `plan-format.md`,
`is_done_without_output` in `verify-log`, and the tests.
