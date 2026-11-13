# Acceptance criteria

- **AC1** — In the review loop, an untracked file one coder call created and a later call of the same loop deletes stays deleted with no tool-fault note; an untracked file that existed before the call, or that appeared between calls without a coder, is restored with the tool-fault note when a coder deletes it. (Phase 1)
- **AC2** — format_files runs `ruff check --fix` and `ruff format` on Python files in a repo whose only ruff setup is a `.pre-commit-config.yaml` with hook ids `ruff` and `ruff-format`; a repo with neither config nor hook runs no ruff. (Phase 2)
- **AC3** — phase_start.py renames an existing `<run folder>/stop.md` to `stop.prev.md`, so the next stop is written as a new file; `review-stop.md` and the relay's stop list are unchanged. (Phase 3)
- **AC4** — `bash tests/run.sh` passes.
