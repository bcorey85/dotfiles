---
type: "Change"
change_type: "changed"
title: "A /code review holds every start-dirty file for the whole phase and holds untracked files no coder of the run wrote"
description: "With another session live in the repo at the phase start, the review holds every file dirty at the run start, and, with a recorded holder or a session live at review, every untracked file no recorded coder wrote; it names a changed held file as a tool fault."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T00:00:00-05:00"}
seq: 1
kind: "fix"
components: ["script/phase-start", "script/code-review-start", "script/code-wait", "shared/handoff-block"]
evidence: ["tests/scripts/test_phase_start.py", "tests/scripts/test_code_review_start.py", "tests/scripts/test_code_wait.py"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest.test_with_a_recorded_holder_a_file_edited_after_the_start_stays_held_and_is_named_as_a_tool_fault"
asked: ""
proof: []
unmeasured: "no intake metric reads a /code review hold; the queue item code-run-hold-drops-when-another-session-edits-its is the only reading"
---

## Change

The phase start records the other live session in the repo, the run's session ids and the start time. With that holder recorded, the review holds every file dirty at the run start for the whole phase, even after its bytes change or the holder ends. It also holds each untracked file that no coder of a recorded session wrote, file by file. Before, a held file dropped out of the hold as soon as its bytes changed or the other session ended.

## Evidence

tests/scripts/test_phase_start.py, tests/scripts/test_code_review_start.py, tests/scripts/test_code_wait.py

## Result

A coder edit to a held file is named as a tool fault in the scope note, the review prompt header and the `code_wait.py review` output. The packet's `tool_fault` field is unchanged. A held file that the phase's own plan section names stays held and is listed on a `held files this phase names:` line and in the scope notes.

## Watch

—

## Back-out

—
