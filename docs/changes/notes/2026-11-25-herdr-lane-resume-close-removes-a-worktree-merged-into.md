---
type: "Change"
change_type: "fixed"
title: "herdr-lane-resume --close removes a worktree merged into the main checkout's branch"
description: "The prune keep checks now also pass a clean lane worktree whose branch is merged into the branch the main checkout has checked out, so the close needs no hand cleanup when lanes merge into a working branch."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T16:00:00-06:00"}
seq: 5
kind: "fix"
components: ["script/herdr-lane-resume", "script/herdr-worktree-prune"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree_prune.py::CheckedOutBranchMergeTest::test_a_clean_worktree_merged_into_the_checked_out_branch_is_removed_with_its_branch"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The prune kept a clean worktree as not merged unless its branch was on `origin/<default>`. A lane merged into the
branch the main checkout has checked out (such as `bench-base`) was kept, and the close left the worktree. The merge
check and the branch delete now accept either ref.

## Evidence

Judgment from the queued report.

## Result

The new test removes a worktree and its branch merged into a checked-out `bench-base`, and keeps an unmerged and a
dirty one.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
