# Acceptance criteria

- **AC1** — A script run on a branch diff lists each added function with exactly one call site whose body is a single call or a single return. (Phase 1)
- **AC2** — The same run lists each added interface or record field with zero reads. (Phase 1)
- **AC3** — The same run lists each added function whose callers all also call a newer helper with the same output. (Phase 1)
- **AC4** — The review loop and refactor branch-prep hand the list to smell-reviewer. (Phase 2)
- **AC5** — A fixture diff with one of each produces three entries; before the change, none. (Phase 1)
- **AC6** — `bash tests/run.sh` passes. (Phase 2)
