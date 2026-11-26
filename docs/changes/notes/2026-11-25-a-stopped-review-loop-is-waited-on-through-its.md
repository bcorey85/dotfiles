---
type: "Change"
change_type: "fixed"
title: "A stopped review loop is waited on through its whole process group"
description: "review_launch waits for the stopped loop's process group to be gone, not only its leader pid, and one stop-wait value of 5 s lives in process_group for review_launch and fork_children."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T16:30:26-06:00"}
seq: 5
kind: "fix"
components: ["script/review-launch", "script/fork-children", "script/process-group"]
evidence: ["tests/scripts/test_review_launch.py", "tests/scripts/test_fork_children.py", "tests/scripts/test_process_group.py"]
watches: []
test: "tests/scripts/test_review_launch.py::StopLoopTest::test_stop_waits_for_a_child_that_outlives_the_leader"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review_launch.stop_loop` and `fork_children.stop_fork_loop` both call `process_group.stop_group`. `stop_loop` reads the loop's process group id before the SIGTERM and waits through `process_group.wait_until_group_gone`, so a child that outlives the leader is waited on. Its own poll loop (`wait_for_exit`, `STOP_POLL_SECONDS`) is gone. `lib/process_group.py` owns one `STOP_WAIT_SECONDS = 5`, which `review_launch` and `fork_children` both read. The settled value is 5 s: long enough for a review loop to remove its worktrees. `review_launch` already used 5 s; `fork_children` used 2 s, and the 2 s value is dropped, so a `fork_children` stop now waits up to 5 s before it reports `signalled`.

## Evidence

A real process group whose leader exits on SIGTERM while its child ignores SIGTERM for a second: `stop_loop` returns only once the group is gone (it returned at once, with the child alive, before the change). The still-running line on stderr is unchanged for a group that outlives the wait. The fork_children tests pass unchanged; new process_group tests cover `stop_group`'s three results (`gone`, `stopped`, `still_running`).

## Result

Before, a launch could start a new loop while a child of the stopped loop still held its worktrees. The two stop waits also disagreed (5 s and 2 s).

## Watch

A launch that prints `the earlier loop ... is still running after 5 s` for a loop whose leader has exited: a child ignores SIGTERM and needs a longer wait.

## Back-out

Revert the Phase 4 commit of one-owner-nov25.
