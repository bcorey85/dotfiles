---
type: "Change"
change_type: "fixed"
title: "a resume test command replaces the full check after a setup fault or an environment gap"
description: "A --test command replaces the default full check when the session's last hand-back for the repo stopped as setup-fault, held an environment-gap full check, or was an overridden run; the packet records check_overridden."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-script", "script/full-check-gate"]
evidence: ["review-resume-ignores-the-caller-s-test-command"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_test_command_on_a_resume_after_a_setup_fault_replaces_the_default_full_check"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_loop_main.py` and `review/full_check_gate.py` run the launch's `--test` commands as the full check,
each on its own, after a setup-fault, environment-gap or overridden hand-back of the same session and repo. A setup fault in those
commands stops the loop as `setup-fault`. `review/handback.py` adds the `check_overridden` packet key. On any other
launch `--test` stays a scoped gate.

## Evidence

A resume after a setup fault ran the same broken default check again and ignored the caller's working test command.

## Result

Twelve new tests in `test_review_loop_script.py`.

## Watch

None.

## Back-out

Revert the commit.
