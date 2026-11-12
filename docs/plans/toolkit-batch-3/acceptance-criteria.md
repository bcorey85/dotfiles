# Acceptance criteria

- **AC1** — pull_keep_index on a branch whose rebase replay re-conflicts where a merge is clean merges the remote and exits 0; a merge that conflicts too keeps the mid-rebase stop. (Phase 1)
- **AC2** — code_review_start exits 1 and names `<run folder>/handoff.txt` when a later phase passes the handoff text an earlier phase read; a rerun of the same phase passes. (Phase 2)
- **AC3** — A fix pass that moves an added block and edits it on the way does not stop the loop; one that deletes the block, or renames a file and reverts the added lines, still does. (Phase 3)
- **AC4** — On a `fix-removed-change` packet, `code_wait.py review` prints a STOP line naming stop.md and `/code resume`, and exits 1. (Phase 4)
- **AC5** — verify-log review logs Step 1 rows when only a converged commit review covers the tree, and still refuses a second branch review. (Phase 5)
- **AC6** — `bash tests/run.sh` passes.
