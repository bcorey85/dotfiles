# Decisions

- 2026-11-25: item 2's owner half came in by merging the orphan branch `fix/plan-check-owner-folder` (merge 687fc5014,
  which adds `plan_format.plan_file_of` and the folder owner read). This plan fixes only the `decide --plan <dir>` crash,
  through `plan_file_of`.
- Standing ruling by agent-evals-c3-owner at 2026-11-25: item 4 done-when narrowed to no commit step in a coder prompt and no stop on a denied coder git write, the run goes on to review uncommitted covers: rewords
- 2026-11-25: item 3's check is split out of `.githooks/pre-commit` into `.githooks/change-file-check`, which owns both
  path patterns. The pre-commit hook and the phase-end script both call it. The whole hook is not run at phase end,
  because a work repo's hook can change files.
- 2026-11-25, ruled by agent-evals-c3-owner (criteria owner `session`): AC5 narrowed to the no-commit rule. The
  denied-git-write sentence is cut: rule meter scenario CS02 (now CK02) scored it 8/8 with the rule and 8/8 without.
  CK01 (the no-commit rule) scored 8/8 on and 1/8 off, so it stays.
