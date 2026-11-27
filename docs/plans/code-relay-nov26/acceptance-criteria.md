# Acceptance criteria

- **AC1** — A test runs the relay on a run folder with only stop.prev.md (no stop.md) after a normal hand-back, and the relay prints the next step, not the say-it-word-for-word instruction. The test fails before the fix. (Phase 1)
- **AC2** — A code-fork that started a skill's forked run in the background cannot hand back before that run reports or finishes: the hand-back gate denies it and names the forked run's agent id. A test shows it, and fails before the fix. (Phase 2)
- **AC3** — `bash tests/run.sh` passes.
