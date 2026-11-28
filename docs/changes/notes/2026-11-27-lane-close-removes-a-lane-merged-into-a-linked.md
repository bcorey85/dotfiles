---
type: "Change"
change_type: "changed"
title: "lane close removes a lane merged into a linked-worktree integration branch"
description: "herdr-lane-resume --close now removes a lane worktree whose branch merged into an integration branch checked out in a linked worktree, along with the lane's leftover untracked plan files, so the user no longer force-removes it by hand."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T19:58:08-06:00"}
seq: 5
kind: "fix"
components: ["script/herdr-worktree-prune", "script/herdr-lane-resume"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_lane_resume.py::EntrylessCloseTest::test_close_removes_a_lane_merged_into_a_linked_integration_worktree_with_its_plan_files"
asked: ""
proof: []
unmeasured: "Script code, not prompt text, so no rule-meter run."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

herdr-worktree-prune counts a tip as merged when it is an ancestor of a branch checked out in a linked worktree of the repo. This holds in `--check`, list mode, `--apply` and the branch delete after a removal. A tip equal to that branch's tip does not count. A branch whose worktree is an open lane gives no credit, and no linked branch gives credit when the lane list cannot be read. On a merged branch, untracked files under `docs/plans/<last segment of the branch>/` no longer keep the tree: `--apply` deletes exactly those files, then runs a plain `git worktree remove`.

## Evidence

Judgment: queue item herdr-lane-resume-close-keeps-a-lane-worktree. The new close test fails against a HEAD export with "would keep ... (not merged)" and passes on the change.

## Result

Full suite: 7959 tests, 0 failed.

## Watch

None: tests pin it.

## Back-out

`git revert` the commit.
