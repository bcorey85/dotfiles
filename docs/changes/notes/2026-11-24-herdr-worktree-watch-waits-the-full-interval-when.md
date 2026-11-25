---
type: "Change"
change_type: "fixed"
title: "herdr-worktree-watch waits the full interval when nothing was polled"
description: "The watcher's final sleep no longer comes out one second short when the shell's SECONDS clock ticks between its start and the sleep and no poll ran."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T16:18:18-06:00"}
seq: 2
kind: "fix"
components: ["script/herdr-worktree-watch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree_watch.py::HerdrWorktreeWatchTest::test_the_watcher_waits_120_seconds_when_no_wait_is_set"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The final sleep was the wait minus the SECONDS difference since start. SECONDS ticks in whole seconds, so with the
toolkit helpers sourced the difference could read 1 with no poll run, and the sleep came out 119. The elapsed time now
counts only when the poll loop ran at least once; with no poll the watcher sleeps the whole wait.

## Evidence

Judgment from the failing test: test_the_watcher_waits_120_seconds_when_no_wait_is_set failed in 4 of 4 runs (expected
sleep "120", got "119").

## Result

The test passes; the tests that count poll time against the wait are unchanged.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
