---
type: "Change"
title: "Format hook skips formatting while a git merge, cherry-pick, revert or rebase is unfinished"
description: "The Stop step of format-changed.py formats nothing while the git dir holds MERGE_HEAD, CHERRY_PICK_HEAD, REVERT_HEAD, rebase-merge, rebase-apply, SQUASH_MSG or MERGE_MSG. Files that a merge brings in are no longer reformatted before the merge commit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T14:48:04-05:00"}
seq: 17
components: ["script/format-changed"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/format-changed.py`:
  - The existing `git rev-parse` call also asks for `--absolute-git-dir`.
  - On Stop, the hook exits 0 and formats nothing while the git dir holds `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge`, `rebase-apply`, `SQUASH_MSG` or `MERGE_MSG`.
  - The UserPromptSubmit snapshot is still written during an operation.
  - An unreachable empty-root check is deleted.
- `tests/scripts/test_format_changed.py`: new tests use a fake `npx`. They check each marker. With real git operations, they check a merge, a merge in a linked worktree, a squash merge and `cherry-pick -n`, and the resume after a merge commit and a squash commit.

## Evidence

Work incident: during a merge in five worktrees, the Stop hook reformatted the files that the other branch brought in. The merge commit took the index as it was and left the reflow as unstaged edits. Each worktree needed a manual cleanup.

A code review of the staged fix found that `git merge --squash` and `git cherry-pick -n` leave only `SQUASH_MSG` or `MERGE_MSG`, so they still got formatted. Both markers were added before install, with tests.

Trade: a `MERGE_MSG` or `SQUASH_MSG` left by an abandoned operation stops formatting until the next commit or reset deletes it.

## Result

Staged 2026-10-21 in the fourth script fix batch. 40 tests pass on the staged copies. The new squash and cherry-pick tests and the older merge-marker tests fail against the installed script. Installed 2026-10-21.

## Watch

None. No intake metric counts formatter edits made during a git operation.

## Back-out

Restore the previous `format-changed.py` and `test_format_changed.py` from the dotfiles history.
