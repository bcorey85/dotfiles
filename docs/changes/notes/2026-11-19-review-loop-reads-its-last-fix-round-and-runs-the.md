---
type: "Change"
change_type: "fixed"
title: "review loop reads its last fix round and runs the changed-file tests"
description: "The review loop gets one reviewer read of its last fix round (asks, plan impacts and nits included, no coder after it), runs the test commands gate_commands derives for the changed test files and reports their counts, and review_fix --file accepts a brief in the session scratchpad."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 7
kind: "fix"
components: ["script/review-loop-script", "script/review-fix", "script/code-step"]
evidence: ["review-loop-ends-on-an-unreviewed-fix-round-and"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_second_round_fix_gets_one_final_read_and_no_coder_after_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

The new `review/review_loop_final_read.py` reads the last fix pass through the same intake as a round
(`review_loop_intake.py`), so its asks and plan impacts reach the packet; its fixes are listed as remaining. The new
`review/review_loop_pass_checks.py` runs the commands `code/gate_commands.derive_gate_commands` derives for changed
test files and puts their counts in the packet. `lib/hook_input.py` accepts a `--file` brief under a session temp root.

## Evidence

A run ended on a fix round no reviewer read, never ran the changed tests, and refused a scratchpad brief.

## Result

Final-read tests in `test_review_loop_script.py`,
`test_gate_commands.py::RunnerScriptRepoTest::test_the_derived_command_runs_in_the_repo_and_reports_counts`, and the
scratchpad brief tests in `test_review_launch.py`.

## Watch

None.

## Back-out

Revert the commit.
