# Acceptance criteria

- **AC1** — The Stop gate passes a closing question that asks before a step that publishes outside the machine (a PR or issue comment, a post to GitHub or a `#<number>` item, a public comment); a question about a local, reversible step still blocks. (Phase 1)
- **AC2** — simplify-prep leaves test, index and style files out of the count and the slices, and slices along module folder lines, never cutting a module folder that fits in one slice. (Phase 2)
- **AC3** — herdr-worktree `--fork` with several helpers missing names all of them in one error, with the exact stow command, and creates nothing. (Phase 3)
- **AC4** — `bash tests/run.sh` passes.
