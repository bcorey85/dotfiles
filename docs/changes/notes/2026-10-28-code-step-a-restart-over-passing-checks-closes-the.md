---
type: "Change"
change_type: "fixed"
title: "code-step: a restart over passing checks closes the phase without a coder"
description: "start --restart over a reviewed, unfinished phase now runs the phase's Automated Verification first and closes the phase when every check passes. Before, it dispatched a fresh coder even when the code was done."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:51:07-05:00"}
seq: 185
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_restart_over_a_reviewed_phase_whose_checks_pass_closes_it_without_a_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A restart over the same unfinished phase whose review ran runs the phase's Automated Verification. When every check
  runs and passes, the phase goes to `finish_phase` with that result, so the checks run once, and no coder is
  dispatched.
- A failing check, an unparsed item, a phase with no runnable check or a restart with run notes dispatches a coder as
  before.

## Evidence

- After a stale run, `start --restart` dispatched a coder for a phase whose code was written and whose checks passed.
  The coder had nothing to do.

## Result

- A restart over finished work closes the phase without a coder.

## Watch

—

## Back-out

Revert the commit.
