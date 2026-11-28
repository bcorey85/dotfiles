---
type: "Change"
change_type: "fixed"
title: "Every capped test run shares one 12 GB tests slice"
description: "The capped test form runs in one shared user slice, tests.slice, capped at 12 GB with no swap, so concurrent suites from many lanes cannot sum past free memory and freeze the machine."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T21:05:59-06:00"}
seq: 7
kind: "fix"
components: ["script/memory-cap-scope", "script/inline-interpreter-hint", "script/full-check", "script/coder-gate", "script/criteria-dry-run", "skill/lane-brief"]
evidence: ["incident", "tests"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::SliceUseTest::test_a_missing_slice_unit_still_runs_the_capped_prefix_in_that_slice"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The capped form in lib/memory_cap_scope.py gains `--slice=tests.slice` and keeps the 8G cap per run. The gate denies a systemd-run test step that names no slice or another slice, and prints the new form. A new stow package, `systemd`, holds `~/.config/systemd/user/tests.slice` (MemoryMax=12G, MemorySwapMax=0). install/stow creates the user unit folder first, stows the package on every platform but mac, and reloads the user manager. The lane brief shows the new form. Both step checks peel a systemd-run wrapper through one helper, test_program_words, and the slice total lives only in the unit file. The review loop's full check (review/full_check.py) now runs inside the same capped slice through `memory_cap_scope.shell_popen_args` when the machine has a systemd user manager, and runs as before when it has none. The coder gate and the criteria dry run now run their test commands through the same `memory_cap_scope.shell_popen_args`, so they too run inside the shared slice where one exists. The gate also reads the value of every systemd-run option that takes one (such as `--description`), so a value is never taken for the test program and a run in another slice cannot pass as capped.

## Evidence

On 2026-11-24 the machine froze: up to three capped suites ran at once (8 GB each) beside 20+ claude sessions on a 30 GB machine with no OOM daemon. 12 GB holds one full suite plus small runs and leaves about 18 GB for sessions and the desktop.

## Result

A missing slice unit does not fail a run: systemd makes the slice on demand with no limit, which the named test proves on this machine.

## Watch

—

## Back-out

Revert the branch's commits and remove `~/.config/systemd/user/tests.slice`.
