# Acceptance criteria

- **AC1** — In a repo with no docs/plans folder, `resolve-task-dir.sh --home <slug>` names a folder under the worktree's git dir, which is outside the tracked tree and off the tmpfs scratchpad. (Phase 1)
- **AC2** — verify-prep finds a plan and criteria file in that git-dir folder with no scratchpad present, by ticket branch and by a ticketless branch. (Phase 1)
- **AC3** — verify-prep's exit-4 message names a ticket path under the git dir, not the scratchpad. (Phase 1)
- **AC4** — A repo with a docs/plans folder resolves exactly as before. (Phase 1)
- **AC5** — eng-spec's task-directory step and verify-branch's exit-4 row name the script-printed paths. (Phases 2, 3)
- **AC6** — `bash tests/run.sh` passes.
