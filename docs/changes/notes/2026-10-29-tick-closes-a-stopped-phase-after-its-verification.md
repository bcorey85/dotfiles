---
type: "Change"
change_type: "fixed"
title: "tick closes a stopped phase after its verification passes"
description: "tick runs the phase's Automated Verification commands before it marks the phase done, and works on a run dropped by abort."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T12:44:13-05:00"}
seq: 265
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_tick_after_an_abort_is_not_held_by_the_archived_plan_edit_guard"
asked: ""
proof: []
unmeasured: "A rare stopped-state path; no intake number reads it."
---

## Change

`tick <phase>` now runs the phase's Automated Verification commands, parsed the way the phase boundary parses them, before it marks the phase done. A failing command makes tick refuse, name the command with its exit code and output, and change neither the plan nor the saved state. Items that name no command stay the user's word, which tick is. When `abort` has dropped the run, tick reads the plan from the newest archived state only when it is readable and names a plan, and no run started after the abort (a run folder other than the archived run's means one did); otherwise tick refuses with the "no saved plan state" message. Tick ignores items that do not parse into a command. Tick also runs whole-suite commands, which the review loop's own run covers in a normal run, because after a stop or an abort nothing else ran the suite. When no verification command ran (no section, only CI or person-tagged items, or only items with no parseable command), the plan's deviation line says the phase was marked done outside the coder, review and verification steps of /code and that no Automated Verification command ran, in place of claiming commands passed. The refusal text tells the user to fix the failure or correct the phase's Automated Verification line in the plan, then run tick again; there is no override. The code skill runs `tick` with a 600-second Bash timeout, so a slow whole suite is not cut off at the default two minutes. The phase-boundary verification stop and tick's refusal now share one `verification_failure_lines` helper, so the boundary stop also prints "(no output)" for a failed command that printed nothing.

## Evidence

A phase fixed outside /code after a review stop could not be closed: after `abort` tick said it needed a plan run, and before `abort` only verbs that redo finished work were offered. The session ticked the plan boxes by hand.

## Result

Tests cover a stopped run, a run after abort, and a failing verification command that leaves the plan unticked.

## Watch

None: no intake number reads this path.

## Back-out

Revert the change to `command_tick`, `stop_for_failed_tick_verification`, `tick_verification_failures` and the new import in `code_step_boundary.py`, the `verification_failure_lines` helper (restore the inline failure-line loop in `stop_for_failed_commands`), the 600-second timeout on the code skill's `tick` line, the `load_aborted_plan_state` helper and `started_after_abort` in `code_step_core.py`, the `run_whole_suites` parameter of `run_verification_commands`, and the changed verification-stop text in `code_step_hooks.py`, the new tick tests, the `put_failing_npx_first_on_path` helper and the passing-`npx` stand-in in `setUp` in tests/scripts/test_code_step.py.
