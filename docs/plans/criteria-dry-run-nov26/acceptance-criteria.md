# Acceptance criteria

- **AC1** — A check whose output shows an unset environment variable, a refused database connection or a missing binary, and no runner summary, reads ENV; a fixture covers each case. (Phase 1)
- **AC2** — The vitest env-guard stop reads ENV. (Phase 1)
- **AC3** — An rg check worded "exits 0" that exits 1 reads RED; a ban that exits 1 still reads GREEN. (Phase 1)
- **AC4** — Every test command the dry run runs is wrapped in the shared memory-cap prefix where the machine has a user systemd scope. (already met; `CappedRunTest`)
- **AC5** — Every phase's checks are listed, closing phases included. (Phase 2)
- **AC6** — `bash tests/run.sh` passes.
