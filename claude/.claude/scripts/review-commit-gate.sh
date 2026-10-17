#!/usr/bin/env bash
# review-commit-gate.sh — a coder dispatch obligates /review before a commit.
#
#   PostToolUse(Agent): a coder dispatch marks the session dirty.
#   PreToolUse(Bash):   `git commit` while dirty asks the user to confirm;
#                       `review-gate-mark clean|dirty` records that state.
#
# The /review, /fix and /code wrappers run `review-gate-mark clean` after a
# converged packet. Hook JSON in, one permissionDecision line out, exit 0 —
# the contract omp's claude-security-bridge.ts reads.
set -Eeuo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

emitted=0
evt=""
ask() {
  emitted=1
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}
on_error_ask() {
  local rc=$?
  [[ "$evt" == PostToolUse ]] && return 0
  if (( rc != 0 && emitted == 0 )); then
    ask "[review-commit-gate] internal error (exit $rc). Allow to run the command anyway."
  fi
  return 0
}
trap on_error_ask EXIT

command -v jq >/dev/null || exit 0
input=$(cat)

evt=$(jq -r '.hook_event_name // ""' <<<"$input")
session=$(jq -r '.session_id // "unknown"' <<<"$input")

state_dir="$HOME/.claude/state/review-gate"
mkdir -p "$state_dir"
state_file="$state_dir/$session"
find "$state_dir" -type f -mtime +2 -delete 2>/dev/null || true

case "$evt" in
  PostToolUse)
    agent=$(jq -r '.tool_input.subagent_type // ""' <<<"$input")
    case "$agent" in
      coder|coder-deep|backend-coder|backend-coder-deep|frontend-coder|frontend-coder-deep)
        echo dirty > "$state_file" ;;
    esac
    ;;
  PreToolUse)
    cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
    if grep -qE '\bgit\s+commit\b' <<<"$cmd"; then
      [[ -f "$state_file" && "$(cat "$state_file")" == "dirty" ]] || exit 0
      ask "[review-commit-gate] Coder work from this session has no converged /review. Allow to commit anyway, or deny and run /review."
    fi
    if [[ $cmd =~ review-gate-mark[[:space:]]+(clean|dirty) ]]; then
      echo "${BASH_REMATCH[1]}" > "$state_file"
    fi
    ;;
esac
exit 0
