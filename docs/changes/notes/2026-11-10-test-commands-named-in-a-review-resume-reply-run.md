---
type: "Change"
change_type: "fixed"
title: "Test commands named in a review resume reply run in the fix run"
description: "review_fix.py launch takes a repeatable --test that the loop runs as a gate command and the relaunch keeps, the resume step puts each test the reply names on the launch line, and the packet says why named tests did not run."
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
- `review_fix.py` / `full_check.py`: when named tests did not run, the packet's scoped-tests line reads `scoped tests not run: <why>` (no fix after the last review, or the loop stopped before the scoped tests).
- `_shared/review-fork-run.md` Resume: test commands the reply names go on the launch line of the run the reply starts, or the stop's next run, one `--test` each.

## Evidence

A /review resume reply named test commands; the run never ran them and the stop said nothing about them. Only the scoped-tests half of the queue item is in this change; the ledger half is out of scope.

## Result

The new launch test fails before the change and passes after. `bash tests/run.sh`: 3363 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
