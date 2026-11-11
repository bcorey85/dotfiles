---
type: "Change"
change_type: "fixed"
title: "Test commands named in a review resume reply run in the fix run"
description: "review_fix.py launch takes a repeatable --test that the loop runs as a gate command and the relaunch keeps, the resume step puts each test the reply names on the launch line, and the loop runs the named tests on every converged run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T19:30:00-06:00"}
seq: 1
kind: "fix"
components: ["skill/review", "skill/fix", "shared/review-fork-run"]
evidence: ["session report: review-loop-skips-requested-scoped-tests-and"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_launch_with_two_tests_passes_each_as_a_gate_command_and_records_them_in_the_relaunch_args"
asked: ""
proof: []
unmeasured: "The review-fork-run.md Resume line is call syntax: it names where the --test flag goes on a launch line the step already runs. No rule-meter run."
---

## Change

- `review_launch.py`: `--test CMD`, repeatable; each goes to the loop as `--gate-command`, an empty one is refused, a repeat dropped, and the relaunch args keep them.
- `review_launch.py` passes `--gates-every-run` to the loop when `--test` is given, so a converged run with no untested fix still runs them (`walk` in `review_loop_script.py`), under a 540 s budget that starts when the named-test run starts and covers that run and its autofix rerun (not the base runs that check a red one); a command that cannot start in the budget left is named in the scoped-tests line (`not run (time budget used up): …`, after a timed-out command's `not run (timeout): …`), or, beside a failure, a command error or a setup fault, in the critical-blocker text (`not run: <cmd>`). The line also carries the runner counts (`; counts: …`). A named command that timed out, never started, or gave a command error or a setup fault stops the loop as `critical-blocker`, even when another command failed as it does on HEAD. A red run stops the loop as `critical-blocker` before commit credit. The packet runs nothing.
- `_shared/review-fork-run.md` Resume: test commands the reply names go on the launch line of the run the reply starts, or the stop's next run, one `--test` each.

## Evidence

A /review resume reply named test commands; the run never ran them and the stop said nothing about them. Only the scoped-tests half of the queue item is in this change; the ledger half is out of scope.

## Result

The new launch test fails before the change and passes after. `bash tests/run.sh`: 3363 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
