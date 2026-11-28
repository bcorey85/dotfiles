# Acceptance criteria

- **AC1** — herdr-worktree starts a lane from the brief alone by default: a run with a brief and no `--fork` opens a headless lane with its lane entry and watcher, and its claude command carries no resume of the parent session. (Phase 1)
- **AC2** — `--fork` stays as an opt-in: a run with `--fork` and a brief still resumes the caller's session as a fork. (Phase 1)
- **AC3** — orchestration.md's lane-start line names the fresh form, with rule-meter on and off counts in the change file. (Phase 1)
- **AC4** — `bash tests/run.sh` passes.
