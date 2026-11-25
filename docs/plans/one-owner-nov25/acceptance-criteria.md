# Acceptance criteria

- **AC1** — With drift already present at HEAD, a toolkit commit that adds no new drift passes the pre-commit hook; a commit that adds a drift line is refused and names that line; a commit that shrinks drift passes. (Phase 1)
- **AC2** — The pre-commit drift check fails closed: with no HEAD commit, or a staged output line that is not a drift problem line, the commit is refused. (Phase 1)
- **AC3** — herdr-worktree-prune is split by concern into modules under scripts/.local/lib, is under 800 lines, and its list, apply and branch modes behave as before. (Phase 2)
- **AC4** — `herdr-worktree-prune --check <path>` prints one JSON verdict for that worktree from prune's own keep rules minus the occupancy checks, and it matches list mode for merged clean, merged dirty, unmerged and squash-merged trees. (Phase 3)
- **AC5** — herdr-lane-resume close holds no merged or dirty check of its own: its entry-less close refuses, changing nothing, exactly when prune's `--check` verdict is keep, and its message carries prune's reason. (Phase 3)
- **AC6** — `bash tests/run.sh` passes. (Branch end)
