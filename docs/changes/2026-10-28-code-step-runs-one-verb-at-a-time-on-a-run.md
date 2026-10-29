---
type: "Change"
change_type: "fixed"
title: "code_step runs one verb at a time on a run"
description: "A second code_step verb started while another runs on the same run stops with the holder's pid and changes nothing; abort still runs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 188
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_resume_while_another_verb_runs_on_the_run_stops_and_changes_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step.py`: every verb but `abort` takes a non-blocking lock on `verb.lock` in the run's state folder. A verb
  that finds the lock held stops with "another code_step verb is running on this run (pid N)" and does not touch the
  state. `abort` never waits on the lock.

## Evidence

- Queue item review-loop-fix-leaves-a-scoped-test-red-and-the: a resumed copy ran beside a live one on the same run.
- The new test fails on the old script: a `resume` while another verb holds the run advances the state.

## Result

- Two verbs never write one run's state at once. The resumed-agent cause itself stays open (follow-up item).

## Watch

—

## Back-out

Revert the commit.
