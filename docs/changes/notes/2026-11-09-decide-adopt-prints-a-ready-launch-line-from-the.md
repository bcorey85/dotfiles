---
type: "Change"
change_type: "fixed"
title: "decide adopt prints a ready launch line from the first run's flags"
description: "When the run has launch flags on record, `review_fix.py decide adopt` writes the first handoff plus the RESOLVED lines to a file and prints the ready launch line, so the follow-up run keeps the first run's repo, range, files and reviewer model."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T19:42:43-06:00"}
seq: 4
kind: "fix"
components: ["script/review-fix", "skill/review", "skill/fix"]
evidence: ["decide-adopt-prints-a-ready-launch-line-from"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_adopting_a_held_plan_impact_of_a_launched_review_prints_a_ready_launch_line_that_reaches_converged"
asked: ""
proof: []
unmeasured: "The review-fork-run.md redispatch line only drops 'from asks-done': it renames where the launch line comes from and adds no behavior rule; the test pins the behavior."
---

## Change

- `review_fix.py decide adopt`: with `relaunch_args` in state, writes `<git dir>/review-fix/adopt-handoff.md` (the first run's handoff plus the RESOLVED, iter, spec_iter and carried-findings lines) and prints `launch --iter <n> <relaunch_args> --handoff <that file> --detach`. Without `relaunch_args` it prints the old hand-built text. An unreadable first handoff stops with the manual recovery.
- `review_fix_asks.relaunch_line` is the one launch-line builder: asks-done's fix run and decide adopt both call it, so both add the first run's touched files to a file-scoped run.
- `review_launch.relaunch_handoff` and `relaunch_args_with_handoff` read and replace the `--handoff` flag of the relaunch args.
- `_shared/review-fork-run.md`: the redispatch line drops "from asks-done".

## Evidence

Queue item `decide-adopt-prints-a-ready-launch-line-from`: a hand-built copy of the first run's flags can drop `--base`, `--file` or `--deep`, so the follow-up run reviews a different scope.

## Result

The new test fails on the old script (the last line is a RESOLVED line, not a launch line) and passes with the change: it launches with `--base`, `--file` and `--deep`, adopts a held plan impact, runs the printed launch line and reaches `render-and-finish` on the converged packet. Suite: `bash tests/run.sh` passes, 3324 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit.
