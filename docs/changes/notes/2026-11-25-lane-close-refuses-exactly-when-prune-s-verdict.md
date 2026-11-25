---
type: "Change"
change_type: "fixed"
title: "Lane close refuses exactly when prune's verdict for the tree is keep"
description: "herdr-lane-resume's entry-less close asks herdr-worktree-prune --check for the tree's verdict and refuses on keep with prune's reason, so a stash, submodule, nested repo or lock now stops a close."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:27:03-06:00"}
seq: 4
kind: "fix"
components: ["script/herdr-lane-resume", "script/herdr-worktree-prune"]
evidence: ["tests/scripts/test_herdr_lane_resume.py", "tests/scripts/test_herdr_worktree_prune.py"]
watches: []
test: "tests/scripts/test_herdr_lane_resume.py::EntrylessCloseTest::test_entryless_close_of_a_merged_branch_with_a_stash_refuses_before_closing"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`herdr-worktree-prune --check <path>` prints one JSON verdict (`remove` or `keep`, with prune's code and reason) for one linked worktree. It uses prune's own keep rules minus the occupancy checks (current worktree, open lane, process, herdr), which a close clears itself. `herdr-lane-resume`'s entry-less close runs it after the working-agent check and before any workspace closes, and refuses on `keep` with prune's reason. Its own merged check and `git status --porcelain` dirty check are gone. `herdr-worktree-prune` was split first (git base and branch mode into `scripts/.local/lib/`) to stay under the size cap.

## Evidence

Prune tests: the `--check` verdict and reason match list mode for merged dirty, unmerged and squash-merged trees; a workspace, agent or open lane on a merged clean tree still gives remove; a non-worktree path exits 1. Lane-resume tests: a stash on a merged branch and a squash-merged branch now refuse before any close.

## Result

Before, close kept its own copy of part of prune's rules and the copies differed: for a stash, submodule, nested repo or lock, close shut the lane's workspace and then prune kept the tree, leaving a worktree with no workspace.

## Watch

A `herdr-lane-resume --close` that refuses with a prune reason for a lane the user expected to close; read the reason before overriding.

## Back-out

Revert the Phase 3 commit of one-owner-nov25; the Phase 2 split can stay.
