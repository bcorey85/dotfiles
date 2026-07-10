#!/usr/bin/env bash
# git-discipline-gate.sh — PreToolUse hook (matcher: Bash).
#
# Deterministic enforcement of three global-CLAUDE.md git rules that the
# generated bash-safety-gate (CB Security Hooks) does not cover:
#   1. git stash          — breaks parallel-agent work and resets staged
#                           files. Read-only inspection (list/show) is fine.
#   2. git commit --amend — rewrites history; only the user decides that.
#   3. git commit on main/master — feature branch first. Exempt when the
#      repo's CLAUDE.md declares "direct-edit repo" (e.g. dotfiles).
#
# Blocks with exit 2 (stderr is fed back to the model). Fails open when jq
# is missing, matching log-skill-use.sh.
set -euo pipefail

command -v jq >/dev/null || exit 0
cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0
[[ -z "$cmd" ]] && exit 0

if grep -qiE '\bgit\s+stash\b' <<<"$cmd" && \
   ! grep -qiE '\bgit\s+stash\s+(list|show)\b' <<<"$cmd"; then
  echo "[git-discipline-gate] git stash is blocked: it breaks parallel-agent work and resets staged files. If stashing is genuinely needed, ask the user — they can run it themselves." >&2
  exit 2
fi

if grep -qiE '\bgit\s+commit\b' <<<"$cmd" && \
   grep -qE '(^|[[:space:]])--amend\b' <<<"$cmd"; then
  echo "[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user explicitly asked. Make a new commit, or ask the user." >&2
  exit 2
fi

if grep -qiE '\bgit\s+commit\b' <<<"$cmd"; then
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  if [[ "$branch" == "main" || "$branch" == "master" ]] && \
     ! grep -qsi 'direct-edit repo' CLAUDE.md; then
    echo "[git-discipline-gate] git commit on $branch is blocked: create a feature branch first (global rule). If committing here is genuinely intended, the user can run it themselves." >&2
    exit 2
  fi
fi

exit 0
