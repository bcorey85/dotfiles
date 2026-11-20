---
type: "Change"
change_type: "fixed"
title: "code resume records the phase base before the phase commits"
description: "phase_start on resume prints the head the run started from when the recorded head is an ancestor of HEAD, and says so when there is no record or the record is not an ancestor; code_wait never returns a packet from an earlier phase's loop folder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 10
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["code-resume-records-phase-base-after-the-phase"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_resume_after_the_phase_was_committed_prints_the_head_the_run_started_from"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/phase_start.py` keeps the start record's head on resume and checks it is an ancestor of HEAD. `code/code_wait.py`
compares the live run's loop folder with the one the record names and returns no packet on a mismatch, naming both.

## Evidence

A resumed phase recorded HEAD after its own commits as the base, so the review diff was empty, and the wait returned
an earlier phase's packet.

## Result

Resume tests in `test_phase_start.py` and loop-folder tests in `test_code_wait.py`.

## Watch

None.

## Back-out

Revert the commit.
