---
type: "Change"
change_type: "changed"
title: "herdr-worktree refuses a branch that another session claimed"
description: "herdr-worktree writes a claim file for the branch before it creates it, and a second session's claim of the same branch fails with a message naming the owner session."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T15:10:00-06:00"}
seq: 1
kind: "fix"
components: ["script/herdr-worktree"]
evidence: ["tests/scripts/test_herdr_worktree.py"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_second_sessions_claim_of_a_branch_fails_naming_the_owner"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`herdr-worktree` claims the branch name in `${XDG_STATE_HOME:-$HOME/.local/state}/branch-claims`, one file per repo and branch holding the claiming session's name, before it creates the branch. A different session's claim of the same branch exits 1 with `branch <name> is already claimed by session <owner>`. The same session may claim again. A claim is stale, and does not block, when its branch is gone and its last claim was more than two minutes ago. A caller with no session name makes no claim. The logic is in `scripts/.local/lib/branch-claim.bash`.

## Evidence

Nine new tests in `tests/scripts/test_herdr_worktree.py`: a second session is refused naming the owner, refused before the branch exists, a claim is scoped to its branch, a claim is scoped to its repo, the same session may re-claim, a stale claim does not block, an old claim still blocks while its branch exists, a caller with no session name makes no claim and is not blocked, a fork refused for a missing claude pane leaves no claim.

## Result

Before, two orchestrator sessions could create the same branch within seconds.

## Watch

—

## Back-out

Revert the commit.
