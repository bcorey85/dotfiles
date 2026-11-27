# Acceptance criteria

- **AC1** — In a shared clone, rule 11 allows a `cat > f` heredoc whose body holds `git commit -m x`. (Phase 1)
- **AC2** — In a shared clone, rule 11 still denies `bash <<EOF` with the same body, and the same body fed to `sh` or piped into `bash`. (Phase 1)
- **AC3** — `bash tests/run.sh` passes.
