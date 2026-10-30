---
type: "Change"
change_type: "changed"
title: "Code-step routes each verb through one typed transition table"
description: "A /code run's state loads as one typed record, every verb and resume step comes from one table of saved state to next step, and each verb writes the state once at its end, so an unknown state stops the verb and a failed verb leaves the state as it was."
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
- A state file loads only when its stage, its stop kind and every key are ones the record names, except a stop
  record's `waitAt`, which loads and is dropped. Any other file stops the verb with a line that names the file and the keys it does not know, and tells the
  user to delete it and run `start`. A field with no value is left out of the file.
- `migrate_old_state` is deleted. A state file in the format before the stop record stops the verb and names its old
  keys.
- `code_step_routes.py` holds the route table: one row per stage, and per stop kind for a stopped run. Each row names
  the step `resume` takes and the one verb it lets run (and `verify` runs once the phase's review converged, at a stage
  marked VERIFY_ON_CLEAN_REVIEW). It replaces the stage-to-step map, the stopped-run route code,
  the per-verb stage guards and the search that named a verb in the fallback stop. A row whose step depends on the
  run's log names what it reads there, and `code_step.py` reads it.
- The same file names each stage's facts: an agent is out, a code agent is out, the plan was edited, `resume` clears
  the say file, a converged review lets `verify` run. They replace six stage tuples in `code_step_core`,
  `code_step_hooks`, `code_step.py` and `saved_handback`.
- The stop texts for a critical blocker, a setup fault and a fix that removed a change no longer need the hand-back
  module to load, so every blocker row has its question.
- A stop for a fix that removed the change under review always lets `review-again` run. Before, it did only when the
  hand-back module loaded.
- A stage set on the record becomes a `Stage` at once, so an unknown one raises where it is set.
- A property test walks every row: each state has one row, each step has a handler, and each verb runs from the rows
  that name it and from no other, except `verify` once the phase's review converged, at a stage marked
  VERIFY_ON_CLEAN_REVIEW.
- Each verb writes `state.json` once, atomically, at its end, and only then prints what to do next. A verb that fails
  part way or exits with an error saves no state file and prints nothing it held, so the saved state never runs ahead
  of a crash. Files written on the way (say.md, question.md, the run log, handback_store rows, dispatch prompts, plan
  edits, the detached review script) stay.
- A state file that changed on disk while a verb ran, as an `abort` from another shell does, is not written over: the
  verb saves no state file, drops its output and stops with a line that names the file. A state file the verb dropped always
  goes, so an abort always ends the run.
- `abort` archives the run as it stood and drops its state file at the verb's end.
- A verb that waits logs the first wait on a resumed agent as a run-log event, so a wait killed part way keeps the time
  the cap counts from.

## Evidence

Census of the code-step fix commits over 14 days: about 34 of 107 came from routing spread over about 15 tables that
read an untyped 40-key dict, where a misspelt or stale key reads as a missing one. Read of `code_step_core.py`: the
old-format migration ran on every load, and no run that old is still open. Read of the old route code: every route,
guard and fallback maps to one row of the table, and the only behavior change is that a fix-removed-change stop always
offers `review-again`. Read of the verbs: each saved the state part way through and printed after, so a crash between
the two left a saved state the session was never told about, and a save after an `abort` brought the run back.

## Result

Measured on the committed code before this review round's fixes: the full suite passed, 4557 tests in 111 files, 0
failed. The code-step, review-loop-script and review-fix test modules, ruff, the code-step complexity check and the
duplicate-code check passed. A state file a run in progress wrote before this change loaded and wrote back the same
values: keys that held null were left out, and keys it lacked were written with their defaults. The route property
test passed, and the walk of every verb path from each start found no failing path in 3204 paths.

Checked on the current tree, with the review fixes and the later integrate merge: the full suite passes, 4647 tests
in 112 files, 0 failed, and ruff passes on the code-step scripts. The suite covers the stop record's `waitAt` key
loading and being dropped, so a resumed agent's cap counts from its first wait after the change; a verb that crashes
after its save leaving the state as it was; and the first wait time of a resumed coder being logged once, at the time
the cap counts from, and surviving a kill during the wait. The complexity check, the duplicate-code check and the
3204-path walk were not re-run on this tree.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commits. Finish or abort any open /code run first: a state file this version wrote leaves out the keys
with no value, and the code before it reads some of them as required.
