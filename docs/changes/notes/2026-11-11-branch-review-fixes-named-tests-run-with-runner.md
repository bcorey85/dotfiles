---
type: "Change"
change_type: "fixed"
title: "Branch review fixes: named tests run in the loop under a time budget, per-finding user rulings"
description: "A converged run with no untested fix runs the named tests under a 540 s budget; every converged run of a launch with --test runs them before commit credit, and a red run blocks credit; --user-ruled is per finding, so only a skip of a finding the user ruled on comes back as an ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T01:39:02-06:00"}
seq: 2
kind: "fix"
components: ["skill/review", "skill/fix"]
evidence: ["branch review: verify-branch code-reviewer NEEDS CHANGES"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_red_gate_command_on_a_converged_run_with_no_fix_stops_the_loop_before_credit"
asked: ""
proof: []
unmeasured: "No skill text changed."
---

## Change

- The usage synopsis names `[--test <cmd>]...`.
- A launch with `--test` passes `--gates-every-run` to the loop: on a converged run with no untested fix the loop runs the named commands through `run_test_commands` before commit credit; a red run, or a named command that timed out, never started, or gave a command error or a setup fault, blocks credit (`critical-blocker`). The named-test run and its autofix rerun share a 540 s deadline that starts when the run starts; the budget covers only those runs, not the base runs that check a red one (each has its own 900 s limit); `coder_gate.scoped_run` takes `budget_seconds` and names commands that never started, also after a command timed out. A loop that gates every run adds the runner counts (`; counts: …`) to each scoped-tests line. A loop that stops before the tests run says so in the scoped-tests line. A readability or stale-prose gate command is no test here, as after a fix. The packet runs no test.
- `--user-ruled N` is repeatable and per finding; the launch record holds the finding texts. `asks_decided_by` is a per-ask list; `--correct` changes the decider only for asks it re-answers.
- `ask_deciders` rejects a saved `asks_decided_by` that is not a list.
- The hand-back's scoped-tests line reads `Scoped tests: <result>` (it also covers a converged run with no fix and a loop that stopped before the run).
- The loop's entry (request, build, run, packet, exit code) moved from `review_loop_script.py` to `review_loop_main.py`; the script still runs by path and calls it.
- The pending-launch deny text of the code-fork Write gate names the file it denies (`review-stop.md`).
- `If no-op, skip` no longer reads as a conditional change.

## Evidence

The branch-wide review found the not-run reason false, named tests skipped when the full check passed, and a `--correct --by user` that made the whole run user-ruled.

## Result

The new tests fail before the change and pass after. `bash tests/run.sh`: 3438 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
