---
type: "Change"
change_type: "added"
title: "Review loop honors a caller's CI test-gate ruling"
description: "A caller that ruled a CI run is the test gate passes `--ci-gate <run>`: the review loop runs no local full check, lint still runs, and the packet says `not run (CI gate: <run>)`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T23:01:24-06:00"}
seq: 3
kind: "fix"
components: ["script/full-check", "script/review-loop-script", "script/code-step", "script/code-review-start", "script/review-launch", "script/review-fix", "script/full-check-gate", "skill/review", "skill/code"]
evidence: ["tests/scripts/test_code_review_start.py", "tests/scripts/test_full_check.py", "tests/scripts/test_full_check_gate.py", "tests/scripts/test_review_launch.py", "tests/scripts/test_review_loop_script.py", "tests/scripts/test_producer_packets.py"]
watches: []
test: "tests/scripts/test_full_check_gate.py::CallerCiRunTest::test_a_loop_step_with_a_ci_run_reports_the_ci_gate_result_and_runs_no_check"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review_fix.py launch` and `code_review_start.py` take `--ci-gate <run>`, which writes a `ci-gate:` header line into the loop's prompt file; a relaunch keeps the flag. The loop reads the header into `ci_run`, and `full_check.run` then starts no check, writes a satisfied receipt and returns `not run (CI gate: <run>)`. The code and review skills tell the fork to pass the flag when the user ruled that a CI run is the test gate.

## Evidence

The test files cover the flag, the header pair, the relaunch, the runner option, the loop's read of the header and a loop step that runs no check under a CI gate, and the packet's full-check line.

`python3 tests/parallel_tests.py test_full_check.py test_review_launch.py test_code_review_start.py test_full_check_gate.py test_review_loop_script.py test_producer_packets.py` passed (828 tests). `bash tests/lint.sh` over the 14 changed .py files passed.

## Result

Before, a caller with a CI test gate still got a local full check from the loop. Now no local check runs and the packet names the CI run.

## Watch

—

## Back-out

Revert the commit, then rerun `build_changes.py --root <worktree>/docs/changes`.
