---
type: "Change"
change_type: "fixed"
title: "mutation seed warning names its owner and stays quiet while the run is live"
description: "The mutation and calibrate lock records its worktree and owner pid; the session-start guard gives a restore command, with an absolute path, only for a stale lock, and a short do-not-restore note for a live one."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:53:23-05:00"}
seq: 104
kind: "fix"
components: ["agent/mutation-tester", "skill/calibrate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_calibration_guard.py::LiveLockTest::test_live_lock_held_by_another_session_gives_no_restore_instruction"
asked: ""
proof: []
unmeasured: ""
---

## Change

- mutation-tester and calibrate write `worktree` (repo top level) and `owner_pid` into the lock.
- calibration_guard joins a relative file onto the worktree, so every path it prints is absolute.
- A lock younger than 60 minutes whose owner process still exists (or that names no owner) gets a note: a seed is in
  progress, do not restore it. A lock past 60 minutes, or whose owner is gone, or whose time stamp does not parse,
  gets the old restore instructions.
- Both lock writers also record `writer` ("calibrate" or "mutation-tester"). The owner pid is the whole session, so
  an interrupted /calibrate left a lock that looked live for an hour, and after /clear read as live from a dead step.
  The preflight now passes `--session-pid "$PPID"`; a lock written by /calibrate with that same owner pid is stale
  (the session is single-threaded, so that step cannot still be running) and gets restored. A lock written by
  mutation-tester stays live in the same session, since it can run in the background. A lock with no `writer`
  keeps the rules above.

## Evidence

- A session started while another session's mutation run held its seed. The guard told it to restore a file it did
  not own, by a path relative to a worktree it was not in. Following it would have undone the live run's mutant.
- Four new tests; they fail on the base tree and the 20 old ones still pass.

## Result

- See the branch's suite run. If `$PPID` in the writer's shell is not a process the guard can see, the owner reads
  as gone and the guard falls back to the old warning.

## Watch

—

## Back-out

Revert the commit.
