# Acceptance criteria

Criteria owner: session (queue item `retire-branch-recap-or-mark-it-legacy-against`).

- **AC1** — The retire-or-legacy choice is made and recorded: retire. (Phase 1)
- **AC2** — No skill names a closing phase other than `/close-branch`: the branch-recap skill and its opencode command are gone, and no skill, script or test under `claude/.claude`, `opencode` or `tests` names `branch-recap`. (Phase 1)
- **AC3** — One recap template remains, in `close-branch` Step 6, and it carries the companion-branches section branch-recap had. (Phase 1)
- **AC4** — An old plan's `Recap` closing phase names `/close-branch`. (Phase 1)
- **AC5** — `bash tests/run.sh` passes. (Phase 1)
