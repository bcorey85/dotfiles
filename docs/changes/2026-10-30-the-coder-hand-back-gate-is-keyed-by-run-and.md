---
type: "Change"
change_type: "fixed"
title: "the coder hand-back gate is keyed by run and dispatch and ends within the hook timeout"
description: "A coder resumed after a stop stays gated, no later run inherits an old gate, and a slow gate run ends with a verdict before the hook timeout instead of passing with none."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T02:20:38-05:00"}
seq: 299
kind: "fix"
components: ["script/coder-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_coder_resumed_after_a_no_change_stop_is_still_gated_at_its_next_hand_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `coder_gate.py set` takes `--run` and `--dispatch`, and the gate file stores both. The hand-back hook looks up the
  coder's dispatch in the run's event log and gates only the coder launched for that dispatch. A coder resumed with
  SendMessage keeps its agent id, so it stays gated. A coder from another run or dispatch passes untouched
  (fail-open: the commands were derived for another dispatch). The 6-hour age limit stays as a backstop.
- `review_coder_report` reads the gate with a new `summary` verb and clears it only after routing, when the step did
  not end on a stop that resumes the same coder. Before, it cleared the gate first, and the resumed coder handed back
  with no checks.
- Every start that gets past its refusals clears any older gate in one place in `command_start`, so a planless start,
  a restart that drops the open run, a closing phase and a start with no derived commands leave none live. A start
  whose coder packet fails clears the gate it set.
- A gate run has a total budget, `GATE_BUDGET_SECONDS`, 600 s under the hook's 3600 s timeout. A command that cannot
  start with at least 60 s left is recorded as `not-started`, and a run with no other failure ends with a `timeout`
  verdict whose stamp names it. Before, three slow commands outlasted the hook, Claude Code killed it, and the hand-back passed with no verdict.
- The TIMED_OUT stamp prints each command's own timeout. Its heading drops "after {timeout_seconds} s", and
  `timed_out` holds a third field per command.

## Evidence

judgment: reading the gate code on the integrate branch showed the clear before a resume-the-coder stop, the gate left
live by a planless start or dropped run, and three 1200 s commands fitting past a 3600 s hook timeout.

## Result

The named test fails before (the gate file is gone after the stop) and passes after. In the same files,
`test_a_planless_start_that_drops_an_open_run_leaves_no_live_gate`,
`test_a_run_over_the_time_budget_names_the_commands_it_did_not_start_and_ends_with_a_verdict` and
`test_a_keyed_gate_gates_only_the_coder_launched_for_its_run_and_dispatch` cover the other cases; each fails on the
old code.

## Watch

None.

## Back-out

In `coder_gate.py`, drop the `--run`/`--dispatch` key, `is_gated_coder`, the `summary` verb, `GATE_BUDGET_SECONDS`,
`HOOK_TIMEOUT_SECONDS`, `MIN_COMMAND_SECONDS` and `NOT_STARTED`, and let `run_commands` return three values again.
In `code_step.py`, have `review_coder_report` clear the gate before routing. Remove `run_coder_gate` from
`code_step_core.py` and its calls in `code_step_start.py`, and the tests. Remove `launched_dispatch`
(`code_step_core.py`) and `start_run`'s `run_id` param, restore `timed_out` to (command, output) pairs, put
`{timeout_seconds}` back in the heading, and undo the `dispatch_id_at` / `script_utils.sortable_unique_id()`
reordering in `start_phase_coder`.
