# Acceptance criteria

- **AC1** — agent-model-guard passes a fork dispatch with no model and still denies an unpinned or opus non-fork dispatch. (Phase 1)
- **AC2** — pull_keep_index on a branch whose upstream is an ancestor of HEAD pulls nothing, keeps HEAD's hash and exits 0; a branch behind its upstream still pulls. (Phase 2)
- **AC3** — refactor simplify-prep lists untracked files of its target and does not stop on a target of only untracked files. (Phase 3)
- **AC4** — refactor_flow's default branch log input lives under the repo's git dir, and close-branch Step 5 names the `log --mode branch` command. (Phase 3)
- **AC5** — log-escape keeps miss_reason in the local escape text file for every stage, and its note says so when the ledger refuses the field. (Phase 4)
- **AC6** — A fix coder's edit to CLAUDE.md, CLAUDE.local.md or AGENTS.md is reverted and reported as a dropped ask, with no user-only ask filed. (Phase 5)
- **AC7** — A review re-run files no approval ask for a saved path whose file has no diff against HEAD. (Phase 5)
- **AC8** — A session asks-done call logs the plain asks and prints their fix run while a user-only ask marked `held` waits for a later `--by user` call. (Phase 6)
- **AC9** — `bash tests/run.sh` passes. (all)
