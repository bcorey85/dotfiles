#!/usr/bin/env bash
# git-discipline-gate.sh — PreToolUse hook (matcher: Bash).
#
# Deterministic enforcement of four global-CLAUDE.md git rules that the
# generated bash-safety-gate (CB Security Hooks) does not cover:
#   1. git stash          — breaks parallel-agent work and resets staged
#                           files. Read-only inspection (list/show) is fine.
#   2. git commit --amend — rewrites history; only the user decides that.
#   3. git commit on main/master — feature branch first. Exempt when the
#      repo's CLAUDE.md declares "direct-edit repo" (e.g. dotfiles).
#   4. git commit/push on a branch still carrying the auto-generated
#      `worktree-` prefix. Not covered by the direct-edit exemption.
#
# Denies via PreToolUse decision JSON. Fails closed on internal error; fails
# open when jq is missing.
set -Eeuo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

emitted=0
deny() {
  emitted=1
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
fail_closed() {
  local rc=$?
  if (( rc != 0 && emitted == 0 )); then
    deny "[git-discipline-gate] internal error (exit $rc) — failing closed. Report this to the user."
  fi
  return 0
}
trap fail_closed EXIT

command -v jq >/dev/null || exit 0
cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || deny "[git-discipline-gate] hook input did not parse — failing closed. Report this to the user."
[[ -z "$cmd" ]] && exit 0

branch=$(git symbolic-ref --short -q HEAD 2>/dev/null || true)

if grep -qiE '\bgit\s+stash\b' <<<"$cmd" && \
   ! grep -qiE '\bgit\s+stash\s+(list|show)\b' <<<"$cmd"; then
  deny "[git-discipline-gate] git stash is blocked: it breaks parallel-agent work and resets staged files. If stashing is genuinely needed, ask the user — they can run it themselves."
fi

if grep -qiE '\bgit\s+commit\b' <<<"$cmd" && \
   grep -qE '(^|[[:space:]])--amend\b' <<<"$cmd"; then
  deny "[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user explicitly asked. Make a new commit, or ask the user."
fi

if grep -qiE '\bgit\s+(commit|push)\b' <<<"$cmd" && [[ "$branch" == worktree-* ]]; then
  deny "[git-discipline-gate] branch '$branch' still carries the auto-generated worktree- prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry."
fi

if grep -qiE '\bgit\s+commit\b' <<<"$cmd"; then
  if [[ "$branch" == "main" || "$branch" == "master" ]] && \
     ! grep -qsi 'direct-edit repo' CLAUDE.md; then
    deny "[git-discipline-gate] git commit on $branch is blocked: create a feature branch first (global rule). If committing here is genuinely intended, the user can run it themselves."
  fi
fi

exit 0
