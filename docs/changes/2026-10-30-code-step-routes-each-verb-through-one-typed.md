---
type: "Change"
change_type: "changed"
title: "Code-step routes each verb through one typed transition table"
description: "A /code run's state loads as one typed record, and every verb and every resume step comes from one table of saved state to next step, so a state the table does not name stops the verb instead of being routed wrong."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T03:44:47-05:00"}
seq: 316
kind: "fix"
components: ["script/code-step", "script/review-loop-script"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_code_step_routes.py::RouteTableTest::test_a_guarded_verb_runs_from_the_rows_that_name_it_and_from_no_other"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_state.py` holds a run as a `RunState` record with a `Stop` record, and names the stages and stop kinds as
  the `Stage` and `StopKind` enums. Every code-step module, `review_loop_script` and `saved_handback` read and write
  fields on the record instead of keys on a dict.
- A state file loads only when its stage, its stop kind and every key are ones the record names. Any other file stops
  the verb with a line that names the file and the keys it does not know, and tells the user to delete it and run
  `start`. A field with no value is left out of the file.
- `migrate_old_state` is deleted. A state file in the format before the stop record stops the verb and names its old
  keys.
- `code_step_routes.py` holds the route table: one row per stage, and per stop kind for a stopped run. Each row names
  the step `resume` takes and the one verb it lets run. It replaces the stage-to-step map, the stopped-run route code,
  the per-verb stage guards and the search that named a verb in the fallback stop. A row whose step depends on the
  run's log names what it reads there, and `code_step.py` reads it.
- The same file names each stage's facts: an agent is out, a code agent is out, the plan was edited, `resume` clears
  the say file, a converged review lets `verify` run. They replace six stage tuples in `code_step_core`,
  `code_step_hooks`, `code_step.py` and `saved_handback`.
- The stop texts for a critical blocker, a setup fault and a fix that removed a change no longer need the hand-back
  module to load, so every blocker row has its question.
- A stage set on the record becomes a `Stage` at once, so an unknown one raises where it is set.
- A property test walks every row: each state has one row, each step has a handler, and each verb runs from the rows
  that name it and from no other.

## Evidence

Census of the code-step fix commits over 14 days: about 34 of 107 came from routing spread over about 15 tables that
read an untyped 40-key dict, where a misspelt or stale key reads as a missing one. Read of `code_step_core.py`: the
old-format migration ran on every load, and no run that old is still open. Read of the old route code: every route,
guard and fallback maps to one row of the table, and the only behavior change is that a fix-removed-change stop always
offers `review-again`.

## Result

The targeted code-step, review-loop-script and review-fix test modules, ruff, the code-step complexity check and the
duplicate-code check pass. A state file a run in progress wrote before this change loads and writes back unchanged.
The route property test passes, and the walk of every verb path from each start finds no failing path in 3204 paths.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commits. Finish or abort any open /code run first: a state file this version wrote leaves out the keys
with no value, and the code before it reads some of them as required.
