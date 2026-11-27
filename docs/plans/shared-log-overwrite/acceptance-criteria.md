# Acceptance criteria

Criteria owner: session (queue item `shared-decisions-log-can-be-written-over-by-a`, Done when).

- **AC1** — A test shows a second session's write to the shared log keeps the first session's unsaved entries (append or refuse with the owner named). (Phase 1)
- **AC2** — `bash tests/run.sh` passes.
