# Acceptance criteria

- **AC1** — Every test file under tests/scripts that reaches the review-gate state sets the state root to a temp folder. (Phase 1)
- **AC2** — A full suite run adds no repo key under the run's temp folder to the real review-gate record files (`*.reviewed`, `*.reviewed-base`, `reviewed-trees.json`). Reworded per Plan Deviations; signed off by the user (Brandon Corey, 2026-11-13 11:32). (Phase 1)
- **AC3** — `bash tests/run.sh` passes.
