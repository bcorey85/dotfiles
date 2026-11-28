# Lane close removes a lane merged into the integration branch

Queue item herdr-lane-resume-close-keeps-a-lane-worktree. `herdr-lane-resume --close` keeps a lane worktree whose
branch merged into an integration branch checked out in a linked worktree (the main checkout is on master). The
lane's leftover untracked plan files also make a plain `git worktree remove` refuse. The keep rules have one owner,
`scripts/.local/bin/herdr-worktree-prune` (its checks, `scripts/.local/lib/worktree_git.py` `merged_into` and
`Repo.merge_targets`, and `scripts/.local/lib/worktree_branches.py` `delete_branch`). herdr-lane-resume calls it
(`--check` before an entry-less close, `--apply` after every close). Fix the rule there, never in a copy.

Source: ~/agent-evals/queue/herdr-lane-resume-close-keeps-a-lane-worktree.md

Criteria owner: session.

## Acceptance Criteria

- AC1: A test in tests/scripts builds a main checkout on master and a linked integration worktree on another branch. It merges a lane branch into the integration branch and runs herdr-lane-resume --close on the lane. The test fails today because the worktree stays. It passes once the close counts a merge into any branch checked out in a linked worktree of the repo and removes the clean worktree, and deletes the lane branch.
- AC2: herdr-worktree-prune counts a tip as merged when it is an ancestor of any branch checked out in a linked worktree of the repo, in `--check`, list mode, `--apply` and the branch delete after a removal. A tip equal to that branch's tip does not count, so a fresh lane cut from the integration branch is still kept as not merged. A branch whose worktree is an open lane (`lanes.py list`) gives no credit, so an integration or parent tree is never read as merged into a lane cut from it; when the lane list cannot be read, no linked branch gives credit. `--check` reads the lane list for this. A test covers the integration tree with an open child lane and the stacked parent with an open child lane: both kept.
- AC3: A worktree whose only untracked files sit under `docs/plans/<lane>/`, where `<lane>` is the last `/` segment of its branch name, counts as clean once its branch is merged. `--apply` deletes exactly those untracked files, then runs a plain `git worktree remove` (never `--force`). A test shows the removal.
- AC4: Any other untracked file, any modified or staged file, or the same plan-folder files on an unmerged branch still keep the tree. A test covers each of the three.
- AC5: The help text of herdr-worktree-prune and the header of herdr-lane-resume name both new rules. The full `bash tests/run.sh` passes.

## What We're NOT Doing

- No lane file target field: the linked-worktree rule covers the integration branch with no new state.
- No change to `--branches` mode, which still lists only branches merged into the compare ref.

## Decision log

- 2026-11-27, lane fork fix/lane-close-integration-merge (session; criteria owner session): the queue item's Done when allows either a linked-worktree branch or a lane-file target; the linked-worktree rule is picked since it needs no new lane state.
- 2026-11-27, lane fork fix/lane-close-integration-merge (session; criteria owner session): plan folder names do not follow the worktree folder name, so `<lane>` is the branch's last `/` segment, the name herdr-worktree gives the folder after the repo prefix.
- 2026-11-27, lane fork fix/lane-close-integration-merge (session; criteria owner session): the review's two asks (an integration or stacked parent tree read as merged into a lane cut from it) are accepted, overriding the earlier rejection. AC2 now gives no credit from a branch whose worktree is an open lane: the integration worktree is not a lane, and a closing lane's entry is gone before the prune runs.
- 2026-11-27, lane fork fix/lane-close-integration-merge (session; criteria owner session): the review's ask about a child lane closed while unmerged (its tree stays with no lane entry, so an idle parent tree reads as merged into it) is left as is. Only a reviewer raised it, the toolkit script rules send such a case to no new code, and the parent's commits stay in the child branch and on origin.
