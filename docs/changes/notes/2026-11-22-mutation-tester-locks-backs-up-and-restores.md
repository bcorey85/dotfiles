---
type: "Change"
change_type: "changed"
title: "mutation-tester locks, backs up and restores through mutation_lock.py"
description: "The calibration lock format has one owner, lib/calibration_lock.py; the calibration guard imports it, and tools/mutation_lock.py gives mutation-tester its lock, backup and restore steps in place of inline jq and shell."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T20:02:28-06:00"}
seq: 36
kind: "fix"
components: ["script/calibration-lock", "script/calibration-guard", "script/mutation-lock", "agent/mutation-tester"]
evidence: ["removal round", "census"]
watches: []
test: "tests/scripts/test_mutation_lock.py::MutationLockTest::test_check_stops_on_a_live_lock_and_leaves_it_alone"
asked: ""
proof: []
unmeasured: "The single Step 4 'Any STOP' bullet (report the verdict, state the stop, hand the printed command to the caller, never retry another way) was merged from two bullets and no meter scenario was run for it; no scenario can make the script's lock unlink fail on demand, so the meter cannot grade that case. The close pass added two more ungraded rules: Step 1's 'keep the --run-id value on the NEXT line for the Step 4 restore line', and Step 4's trigger 'runs only after lock printed NEXT: apply the mutation; when lock stopped, there is nothing to restore'."
---

## Change

`claude/.claude/scripts/lib/calibration_lock.py` owns the lock path, the legacy path, the stamp format, the lock view and the liveness read. `gates/calibration_guard.py` imports it with its output and exit codes unchanged. `tools/mutation_lock.py` runs the lock, backup and restore steps that `mutation-tester.md` used to spell out in jq and shell; both the claude and the opencode agent files call its `check`, `lock` and `restore` verbs. The lock path reader is `calibration_lock_path` and the argument parser builder is `mutation_lock_parser`: the toolkit's duplicate-code check refuses a top-level function name defined in two files, and master's `pull_keep_index.py` and `lanes.py` already hold `lock_path` and `build_parser`.

## Evidence

The lock layout lived three times: in the guard, in the agent's jq writer and in the agent's restore prose, with a precondition count that did not match its list.

## Result

`tests/scripts/test_calibration_lock.py` and `tests/scripts/test_mutation_lock.py`.

## Watch

None.

## Back-out

Revert the commits.
