# Acceptance criteria

Owner: session

- **AC1** — Close and prune remove a clean worktree whose branch is merged into the branch the main checkout has checked out, though not into origin's default branch. (Phase 1)
- **AC2** — A worktree not merged into either ref, and a dirty one, is still kept. (Phase 1)
- **AC3** — `bash tests/run.sh` passes.
