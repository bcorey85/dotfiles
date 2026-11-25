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
