#!/usr/bin/env bash
# review-commit-gate.sh — mechanizes the global-CLAUDE.md rule "a coder
# dispatch obligates /review before /commit". The prose version of this rule
# needed three restatements and still leaked; this hook makes it deterministic.
#
# Registered twice in settings.json:
#   PostToolUse (matcher: Agent) — tracks per-session review state:
#       coder dispatch    -> "dirty" (unreviewed coder work exists)
#       reviewer dispatch -> "clean" (a review pass has run)
#   PreToolUse  (matcher: Bash)  — blocks `git commit` while state is dirty.
#
# The review signal is a code-reviewer / test-intent-reviewer Agent dispatch,
# which every /review path ends in (both /code-chained and standalone).
# Gating the Bash `git commit` chokepoint covers every invocation route
# (model Skill call, user-typed /commit, ad-hoc commit).
#
# review-loop is special-cased: its PostToolUse event fires LAST (after every
# nested coder/reviewer event), so an unconditional "clean" here would erase
# the dirty state a cap-reached/aborted loop deliberately leaves behind. The
# loop's returned packet is the authority: `status: converged` -> clean,
# anything else (cap-reached, critical-blocker, plan-impact, or an unreadable
# response) -> dirty. Fail-closed: a blocked commit costs one /review; an
# unblocked commit over outstanding findings is the failure this hook exists
# to prevent.
#
# One-shot override for a USER-approved trivial skip (consumed on use):
#   touch ~/.claude/state/review-gate/<session_id>.skip
set -euo pipefail

command -v jq >/dev/null || exit 0
input=$(cat)

evt=$(jq -r '.hook_event_name // ""' <<<"$input")
session=$(jq -r '.session_id // "unknown"' <<<"$input")

state_dir="$HOME/.claude/state/review-gate"
mkdir -p "$state_dir"
state_file="$state_dir/$session"
skip_file="$state_dir/$session.skip"

# Prune stale session state so the dir never grows unbounded.
find "$state_dir" -type f -mtime +2 -delete 2>/dev/null || true

case "$evt" in
  PostToolUse)
    agent=$(jq -r '.tool_input.subagent_type // ""' <<<"$input")
    case "$agent" in
      coder|coder-deep|backend-coder|backend-coder-deep|frontend-coder|frontend-coder-deep)
        echo dirty > "$state_file" ;;
      review-loop)
        resp=$(jq -r '.tool_response // "" | tostring' <<<"$input")
        if grep -qE 'status:[[:space:]]*converged' <<<"$resp"; then
          echo clean > "$state_file"
        else
          echo dirty > "$state_file"
        fi ;;
      code-reviewer|code-reviewer-deep|test-intent-reviewer)
        echo clean > "$state_file" ;;
    esac
    ;;
  PreToolUse)
    cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
    grep -qE '\bgit\s+commit\b' <<<"$cmd" || exit 0
    [[ -f "$state_file" && "$(cat "$state_file")" == "dirty" ]] || exit 0
    if [[ -f "$skip_file" ]]; then
      rm -f "$skip_file"
      exit 0
    fi
    echo "[review-commit-gate] A coder subagent ran this session and no code review has run since. Run /review before committing. Only if the USER explicitly approved skipping review for a trivial diff, create the one-shot override and retry: touch $skip_file — never create it on your own judgment." >&2
    exit 2
    ;;
esac
exit 0
