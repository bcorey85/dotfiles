---
type: "Change"
change_type: "fixed"
title: "a phase with a Session phase line runs in the session, and a packet carries the phases it cites"
description: "A /code phase whose section has a `**Session phase**: <agent>` line now stops for the session instead of going to a coder, plan-format.md tells plan writers to add the line, and the session stop and the coder packet both add the lines of each phase that the phase reuses with 'same as Phase N'."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-30T12:00:00-05:00"}
seq: 385
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_phase_with_a_session_phase_line_stops_for_the_session_and_closes_with_session_done"
asked: ""
proof: []
unmeasured: "A rare plan shape; no intake number reads it. A phase that dispatches a coder-class agent (coder, coder-deep, backend- or frontend- forms, any name ending -coder) keeps the coder path, so the review-commit gate never meets a session phase's commit line for those names."
---

## Change

- `start` reads a phase whose section has a `**Session phase**: <agent>` line, and no **File**: or **Files**: entry, as a
  session phase. The shared plan template (`_shared/plan-format.md`) tells plan writers to add the line to a phase that
  only the /code session can run. It saves the run at a new `session` stage, prints a `stop` that names the
  agent and shows the phase text. No coder is dispatched: a coder has no Agent tool and may not commit.
- The stop tells the session to dispatch the agent, do the phase's steps without the commit, then invoke Skill code
  with `session-done <phase>`. That verb (guarded by the `session` stage, like `skill-done` by the `skill` stage) runs
  the phase's Automated Verification, marks the phase done and prints the commit command, so the plan edit is in the
  commit. It writes no deviation line and never goes through `tick`, which stays the user's word. `resume` on the
  stage says the stop again. The verb is in the `/code` skill's verb list and in `herdr-phase-change`.
- `verify` after a failed Automated Verification of a session phase also skips the review gate (state field
  `no_review`).
- `plan_format.session_only_agent` is one line-anchored regex (`SESSION_PHASE_LINE`) over the section. It returns the
  agent from the line, and None for a section that also has a **File**: entry or whose agent is a coder-class name.
  A phase without the line keeps the coder path, whatever its steps say.
- The session stop and the coder packet both add the plan range of each other phase that the phase text cites with
  "same as Phase N" (`plan_format.cited_phases`), so a reused mutant list reaches the session or the coder.

## Evidence

judgment: a mutation-tester phase went to a coder, which stopped on a toolkit fault with no edits, and its packet left
out the earlier phase it reused.

## Result

The named test fails before (the output is a coder dispatch) and passes after. The packet test
`tests/scripts/test_coder_packet.py::CoderPacketTest::test_a_phase_that_says_same_as_an_earlier_phase_gets_that_phases_lines`
fails before and passes after.

## Watch

None.

## Back-out

Remove `start_session_phase`, `emit_session_phase` and their call in `start_plan_run`, the `session` stage with its
route, `resume_session_phase` with its `STEPS["session-phase"]` entry (`code_step.py`) and the `STAGE_FACTS[Stage.SESSION]`
entry (`code_step_routes.py`), `command_session_done` and the `session-done` verb entries (`code_step.py` verbs map, `VERB_USAGE` and
docstring; `ROUTES` in `code_step_routes.py`; `VERB_REFUSALS` in `code_step_review.py`;
`VERB_WORDS_THAT_CARRY_INPUT` in `code_step_start.py`; `code_step_usage.py`; the `/code` `SKILL.md`; and
`scripts/.local/bin/herdr-phase-change`), the
`no_review` field in `code_step_state.py` and the `not state.no_review` guard in `finish_phase`
(`code_step_boundary.py`), `session_only_agent` with its `SESSION_PHASE_LINE` marker regex in `plan_format.py`, the
`**Session phase**` rule in `_shared/plan-format.md`, and the `plan_format.cited_phases` call that prints cited ranges in
`coder_packet.py` and in `emit_session_phase`. Keep `plan_format.SAME_AS_PHASE` if the packet's cited ranges stay.
Remove the tests that name them.
