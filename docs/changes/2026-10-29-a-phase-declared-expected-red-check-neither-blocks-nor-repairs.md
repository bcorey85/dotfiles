---
type: "Change"
title: "A phase's declared expected-red check neither blocks nor repairs"
description: "A plan phase can declare `Expected red: <step> until Phase <id>`; the review gate then leaves that step out of the full check, repairs never edit files only a later phase names, and `/code`'s new `guide` verb records the main session's guidance for every later dispatch of the run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:00:00-05:00"}
seq: 273
kind: "fix"
components: ["script/full-check", "script/review-loop-script", "script/code-step", "agent/review-loop", "skill/code", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_check_the_phase_declares_expected_red_converges_with_no_repair"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/expected_red.py`: one grammar for the `Expected red: `<step>` until Phase <id>` line, the plan-check refusals
  (bad form, outside a phase, unknown phase, a phase not later than its own, no check, a step the check does not
  hold), the check with the expected-red steps left out, and the files only a later, not-done phase names.
- `full_check.py --plan --phase`: leaves out the phase's expected-red steps and prints each; a whole expected-red check
  gives `not run (expected red until Phase <id>)`. Once that phase is done the step runs and blocks again.
- `review_loop_script.py`: runs the phase's check the same way, and stops with `critical-blocker` when a repair edits a
  later-phase file. A file the current phase names too stays editable.
- `code_step`: `plan check` refuses a bad line; the coder hand-back hook denies an edit to a later-phase file; the
  review dispatch carries `later-phase files:`; the new `guide <text>` verb stores guidance in the run state, so it
  survives a resume, and every later review and coder dispatch carries it. It never changes the task or the plan.
- `plan-format.md` (read by eng-spec) states the line and puts it in the phase template; `review-loop.md` and the
  opencode port take the two new inputs.

## Evidence

- A phase whose tests are red by design until a later phase made the review gate block and repair, and the repair
  edited files the plan assigned to the later phase. Guidance from the main session reached a running `/code` only
  through a restart.

## Result

- The named test fails before (the loop repairs the expected-red failure) and passes after. Also fail-first:
  `test_expected_red.py`, `test_full_check.py::PhaseExpectedRedTest`, `test_code_step_expected_red.py` and
  `test_review_loop_gate.py::...::test_a_check_the_phase_declares_expected_red_counts_as_run`.

## Watch

—

## Back-out

Revert the commit.
