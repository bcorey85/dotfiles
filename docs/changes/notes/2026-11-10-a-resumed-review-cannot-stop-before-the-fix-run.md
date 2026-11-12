---
type: "Change"
change_type: "fixed"
title: "A resumed review cannot stop before the fix run asks-done printed"
description: "asks-done marks its printed fix run pending, the code-fork Write hook refuses review-stop.md until a launch with that findings file starts, so a resumed /review always ends with a review round over the asks it applied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:36:18-06:00"}
seq: 1
kind: "fix"
components: ["skill/review", "skill/fix", "shared/review-fork-run"]
evidence: ["session report: review-resume-skips-final-round"]
watches: []
test: "tests/scripts/test_fork_write_scope.py::PendingLaunchTest::test_review_stop_is_denied_while_a_fix_run_is_pending_and_the_reason_names_the_line"
asked: ""
proof: []
unmeasured: "No skill text changed; the hook enforces the existing resume rule."
---

## Change

- `review_fix_asks.write_unprinted_fix_run` sets `asks_launch_pending` (the launch line) in the fix state when it stores a launch line.
- `review_launch.command_launch` clears it right after argument parsing when `--fix` names the pending findings file, so a launch that then fails still lets the fork write its stop.
- `review_fix.new_state` carries the flag only into a repeat of its own packet, or while the packet that printed it waits; a packet of another review run starts without it, so a stale flag never blocks that run's stop write.
- `gates/fork_write_scope.py` denies a code-fork Write of `<run folder>/review-stop.md` while `<git dir>/review-fix/state.json` holds the flag, and names the launch line. An unreadable or non-object state denies and names the file.
- State and stop file names move to import-free `lib/review_fix_names.py` and `lib/stop_file_names.py`, so the gate imports no heavy module.

## Evidence

A resumed /review ran asks-done, which printed `ACTION: redispatch` with a launch line; the fork wrote review-stop.md and ended. No review round covered the fix, and the commit gate blocked.

Hook time, median of 15: bare `python3 -c pass` 7.8 ms, non-code-fork Write 15.6 ms, matched code-fork review-stop.md Write 24.9 ms.

## Result

The new PendingLaunchTest cases fail before the change and pass after. `bash tests/run.sh`: 3358 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit: the flag, the clear in launch and the gate check go together.
