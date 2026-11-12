# Acceptance criteria

- **AC1** — verify-prep given a plan.md path or its folder resolves the plan and the folder's acceptance-criteria.md with no ticket file, and reports criteria owner `plan`. (Phase 1)
- **AC2** — A plan folder with neither ticket nor criteria still fails loudly. (Phase 1)
- **AC3** — After a branch review was logged on an earlier tree, a converged /review of the current tree makes verify-prep report the review as ran. (Phase 2)
- **AC4** — refactor branch-prep lists uncommitted and untracked files and bounds the reviewer to the work tree against the merge-base. (Phase 3)
- **AC5** — pull_keep_index on a branch rewritten locally pulls nothing and exits 0; a branch another machine pushed to still pulls. (Phase 4)
- **AC6** — The criteria dry run reports a tool-shim failure as ENV, and the escaped and unescaped forms of an rg ban get the same label. (Phase 5)
- **AC7** — An edit to the gate replay corpus leaves its other lines unchanged by the formatter. (Phase 6)
- **AC8** — `bash tests/run.sh` passes.
