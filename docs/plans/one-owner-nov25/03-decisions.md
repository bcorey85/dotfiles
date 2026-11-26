# Decisions

- 2026-11-25, ruling by agent-evals-c3-owner (the orchestrating session): drop queue items
  quality-check-cap-keeps-its-own-copy-of-the-shell and move-review-launch-wait-for-exit-onto-process from this lane,
  because another session claimed both on bench-base after the lane started; leave their queue status alone.
- 2026-11-25, ruling by agent-evals-c3-owner: the drop above is reversed. The session that claimed
  quality-check-cap-keeps-its-own-copy-of-the-shell and move-review-launch-wait-for-exit-onto-process handed both to
  this lane; their "already running" status counts as this lane's claim. Both are in scope.
- 2026-11-25, ruling by agent-evals-c3-owner: quality-check-cap-keeps-its-own-copy-of-the-shell is split. This lane
  moves memory_cap_scope's systemd-run option walk onto shell_command, with its test. The
  quality_check_cap.without_systemd_run half, which exists only on fix/asks-done-scripts-claude-md, goes to a new queue
  item that starts once that branch merges.
- 2026-11-25, this session: the pre-commit hook compares the drift checker's stderr lines (staged against HEAD)
  rather than adding a JSON mode to `toolkit_drift.py`, because that script lives in agent-evals, outside this lane.
- 2026-11-25, this session: prune gains `--check` after a split by concern (git base, branch mode) rather than a cut,
  because it sits at 991 of the 1000-line cap and the keep rules must stay with prune, their one owner.
- 2026-11-25, this session (branch-wide review): `shell_command.command_options` loses its `start` parameter, which
  only a test used (Phase 5 step 1 named `start=1`); `git_option_values` is renamed `option_values`, since it now
  reads any command's pairs (Phase 5 step 1 said rename nothing). Both narrow the plan's wording; the AC stays met.
- 2026-11-25, this session (branch-wide review): prune no longer re-imports `checked_out_branches`,
  `delete_one_branch` and `parse_worktrees` for the tests; the prune tests import them from their owner modules
  (Phase 2 step 3 kept them reachable on prune). No behavior change.
- 2026-11-25, this session (branch-wide review ask): the pre-commit hook copies every staged line as added when the
  HEAD problem file is empty, rather than relying on `grep -f` of an empty file, so a BSD grep cannot fail open.
- 2026-11-25, ruling by agent-evals-c3-owner: accept the capped /review of the two refactor docstring edits
  (`fork_children.py`, `shell_command.command_options`) and resume; its one finding (a line over 120 characters) is
  fixed, and lint and the touched tests pass.
- 2026-11-25, ruling by agent-evals-c3-owner: the merge /review's ask on pre-commit line 61 (a multi-name
  `toolkit_drift` skill line compared whole, so a commit that shrinks it is refused) goes to agent-evals, already
  queued as toolkit-drift-check-refuses-a-commit-that-fixes; the hook stays as it is in this lane.
- 2026-11-25, ruling by agent-evals-c3-owner: accept the capped merge /review (base 1bc84d3b3); keep its three
  fixes and fix its open smell (unused setup in `test_review_launch.py`); touched tests and lint pass.
