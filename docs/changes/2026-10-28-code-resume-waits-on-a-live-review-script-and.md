---
type: "Change"
title: "code resume waits on a live review script and names the changed phase text"
description: "resume no longer calls a run stale while its review script is alive, and a stale question quotes the phase lines that changed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T14:10:00-05:00"}
seq: 198
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_resume_while_the_review_script_runs_does_not_call_the_phase_stale"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The stale-phase check returns nothing while the run's review script is alive, at any stage, so `resume` waits for the script, and `start`'s open-run refusal no longer calls the run stale.
- A stale-phase question lists up to three lines that were removed from the phase and up to three that replaced them.

## Evidence

- A review script ten minutes into its run was met by a stale-run question on every resume; answering with a restart would have killed the review. Why the verdict fired on text the reporter saw as unchanged is not covered here: the stale rule itself is untouched.
- Three new tests fail on the old script: the live-script resume, the review-cap live-script resume (`test_a_resume_at_the_review_cap_while_the_review_script_runs_does_not_call_the_phase_stale`) and the changed-lines question.

## Result

- A running review is waited on. A stale verdict says which text changed.

## Watch

—

## Back-out

Revert the commit.
