---
type: "Change"
change_type: "fixed"
title: "Scoped test gate runs the autofix formatters before it stops"
description: "The review loop no longer stops a finished phase on format-only scoped-test failures: a red scoped run gets one autofix formatter pass and one rerun, and only a run still red stops the loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T13:28:06-06:00"}
seq: 452
kind: "fix"
components: ["script/review-loop-script", "skill/code", "skill/review"]
evidence: ["defect report"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_scoped_run_red_only_on_format_errors_the_autofix_clears_does_not_stop_the_loop"
asked: ""
proof: []
unmeasured: ""
---

## Change

`run_test_commands` in `review_loop_script.py` now calls `autofix_touched_files()` when the scoped test or lint run is red. If a formatter changed a file, it reruns the scoped commands once. Only a run still red stops the loop as `critical-blocker`. `recheck_full_check` already takes this step for the full check; both now share the one helper.

## Evidence

The fix coder runs with the format hook off. On bench tickets its last fix left prettier-only lint errors, and the scoped gate stopped a finished review for a human. Each resume cleared the errors, then the next fix coder wrote new ones, so one phase stalled across several sessions.

## Result

Two new tests: a red run the autofix clears passes with no blocker, and a run still red after the autofix stops the loop. Both fail before the change and pass after. The full dotfiles suite passes (3011 tests).

## Watch

—

## Back-out

Revert the commit. The scoped gate then stops on the first red run again.
