# Sourced by herdr-lane-resume, herdr-worktree, herdr-phase-change and herdr-worktree-watch, and by
# scripts/.local/lib/lane_list.py (for herdr-lane-sweep and herdr-worktree-prune).
# Sets lanes_cli and session_pane, the toolkit scripts' paths, each overridable by an environment variable.

# shellcheck disable=SC2034
lanes_cli=${HERDR_LANES_CLI:-$HOME/.claude/scripts/tools/lanes.py}
# shellcheck disable=SC2034
session_pane=${HERDR_SESSION_PANE:-$HOME/.claude/scripts/tools/session_pane.py}
