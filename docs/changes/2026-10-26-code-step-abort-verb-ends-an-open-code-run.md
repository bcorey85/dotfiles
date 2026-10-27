---
type: "Change"
title: "code-step abort verb ends an open /code run"
description: "code_step.py abort drops the open /code run: it archives state.json, clears the say, question and coder-gate files, and prints what it dropped, so the next start begins a fresh run with no restart flag."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T09:26:26-05:00"}
seq: 49
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_start_after_abort_begins_a_fresh_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step.py` gains an `abort` verb. With an open run it settles the criteria guard, clears `say.md`, `question.md` and the coder gate, and renames `state.json` to `aborted-<UTC time>.json` in the same folder. It prints the phase and stage it dropped, an open dispatch (the agent id, or a launch that was not logged), the files changed since the run's baseline that stay in the working tree, and the archive path. It keeps `ruled-asks.json` and the event logs, and never touches the working tree. With no open run it says so and writes nothing. It refuses arguments. `start abort` names the verb instead of taking `abort` as task text.

The `/code` skill routes the task text `abort` to the verb.

Before, the only way out of a stuck or unwanted run was a `start` with the restart flag or deleting the state folder by hand.

## Evidence

judgment: a session had no clean way to drop a /code run it no longer wanted. All five new tests fail on the base commit and pass after: `test_start_after_abort_begins_a_fresh_run`, `test_abort_with_no_open_run_says_so_and_writes_no_file`, `test_abort_archives_the_state_and_keeps_the_ruled_asks_and_names_the_open_dispatch`, `test_abort_refuses_extra_arguments_and_keeps_the_run`, `test_start_names_the_abort_verb_when_given_it_as_task_text`.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Revert `command_abort`, `abort_dropped_lines`, `changed_since_baseline` and the `abort` entries in `main`, `VERB_USAGE`, `first_word_is_verb` and the docstring in `code_step.py`; the five tests in `test_code_step.py`; and the `abort` sentence in step 1 of the `/code` skill.
