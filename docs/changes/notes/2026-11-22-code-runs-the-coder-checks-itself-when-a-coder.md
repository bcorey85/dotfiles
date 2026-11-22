---
type: "Change"
change_type: "fixed"
title: "Code runs the coder checks itself when a coder skips the hand-back"
description: "A coder that ends without handing back through the gate no longer sends failing checks to review: /code runs the gate's checks itself and sends any failure back to the coder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:53:40-06:00"}
seq: 22
kind: "fix"
components: ["script/coder-gate", "skill/code"]
evidence: ["peer report"]
watches: []
test: "tests/scripts/test_coder_gate.py::CoderGateEnvironmentTests::test_finish_runs_the_commands_when_no_coder_handed_back_and_keeps_the_gate_on_a_failure"
asked: ""
proof: []
unmeasured: "The /code step-3 sentence changed from `clear` to `finish` plus 'on exit 1, do the step its last line names'. No rule-meter fixture covers the fork's hand-back step, so the meter cannot grade the wording; the script exit code carries the behavior."
---

## Change

`coder_gate.py` has a new verb, `finish`, which `/code` step 3 runs in place of `clear` right after the coder returns. When a coder handed back through the SubagentHandback hook, `finish` acts as `clear`. When no coder did (it ended its turn without the call, so the hook never ran), `finish` runs the stored check commands itself. A pass, timeout, setup fault or command error deletes the gate. A real failure keeps the gate, prints the failing tests and output tails, and exits 1; its last line tells the fork to send that output to the coder and run `finish` again. After three failing runs it stops refusing, deletes the gate, and says the review handoff lists the failure under `flagged`. The `clear` before the first phase is unchanged. The coder packet still tells the coder to skip checks, which now holds: the checks run at hand-back or at `finish`.

## Evidence

A /code phase with the coder on haiku: the coder's packet said the hand-back hook runs the checks, the coder ended without calling SubagentHandback, `clear` printed "never ran, no coder handed back through it", and a new test file reached the review loop with a typecheck and a lint error. The loop spent its one repair and stopped at critical-blocker.

## Result

The new test fails on the old script and passes on the new one. Four more tests pin the no-gate, pass, hook-already-ran and cap paths; all 44 tests in the class pass. Full `tests/run.sh`: 5248 tests in 178 files, one failure (the rule-anchors hash for the edited skill block), fixed and re-run green; ruff clean.

## Watch

None: the intake has no count of coder hand-backs that skipped the gate.

## Back-out

Put `clear` back in `/code` step 3 and delete `finish_gate`, `_finish_under_lock` and the five `finish` tests.
