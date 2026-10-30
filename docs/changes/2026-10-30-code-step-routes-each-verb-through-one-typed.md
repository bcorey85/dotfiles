---
type: "Change"
change_type: "changed"
title: "Code-step routes each verb through one typed transition table"
description: "A /code run's state loads as one typed record that refuses a key, stage or stop kind it does not know, so a state file another version wrote stops the verb instead of being routed wrong."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T03:44:47-05:00"}
seq: 316
kind: "fix"
components: ["script/code-step", "script/review-loop-script"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_code_step_state.py::StateFileTest::test_a_key_the_record_does_not_name_stops_the_load_and_is_named"
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

## Evidence

Census of the code-step fix commits over 14 days: about 34 of 107 came from routing spread over about 15 tables that
read an untyped 40-key dict, where a misspelt or stale key reads as a missing one. Read of `code_step_core.py`: the
old-format migration ran on every load, and no run that old is still open.

## Result

The targeted code-step, review-loop-script and review-fix test modules and ruff pass. A state file a run in progress
wrote before this change loads and writes back unchanged.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commits. Finish or abort any open /code run first: a state file this version wrote leaves out the keys
with no value, and the code before it reads some of them as required.
