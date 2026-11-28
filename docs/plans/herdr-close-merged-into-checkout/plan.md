# Close removes a lane worktree merged into the main checkout's branch

`herdr-lane-resume --close` keeps a clean lane worktree as not merged when its branch is merged into the branch the
main checkout has checked out (for example `bench-base`) but not into `origin/<default>`. Fix the owner:
`check_merged` and `start_up` in `scripts/.local/bin/herdr-worktree-prune`, `Repo` in
`scripts/.local/lib/worktree_git.py`. `herdr-lane-resume` stays unchanged.

## Phase Status

- [x] Phase 1: a clean worktree merged into the main checkout's checked-out branch is removed (risk: low)

## Phase 1: merge check reads the main checkout's branch too

`Repo` gains optional `checkout_name` and `checkout_hash`, filled by `start_up` from the main worktree (None when
detached or bare). The merge check passes when the tree head is an ancestor of the compare hash or of the checked-out
branch; the keep message names both refs. Branch deletion after the removal uses the same check, so the close does not
end with a failed branch delete. Branch mode (`for-each-ref --merged`) is unchanged.

#### Automated Verification

- `bash tests/run.sh`
