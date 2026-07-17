#!/usr/bin/env bash
# review-commit-gate.sh — mechanizes the global-CLAUDE.md rule "a coder
# dispatch obligates /review before /commit". The prose version of this rule
# needed three restatements and still leaked; this hook makes it deterministic.
#
# Registered twice in settings.json:
#   PostToolUse (matcher: Agent) — ARMS the gate:
#       coder* dispatch      -> "dirty" (unreviewed coder work exists)
#       review-loop dispatch -> "dirty" (a loop is in flight; outcome unknown)
#   PreToolUse  (matcher: Bash)  — two jobs:
#       blocks `git commit` while state is dirty
#       records `review-gate-mark clean` — the ONLY clean transition
#
# Why Agent events never write "clean": the harness launches subagents async
# (even when dispatched with run_in_background: false), so PostToolUse fires at
# LAUNCH with a metadata stub — the reviewer hasn't run yet and the loop's
# packet is never in .tool_response. Any clean-on-Agent-event rule is therefore
# either premature (reviewer launch) or unreachable (packet parse). The packet
# reaches the MAIN session later via task-notification; the /review, /fix, and
# /code wrappers route on its `status` there and run
# `bash ~/.claude/scripts/review-gate-mark clean` ONLY after rendering a
# `converged` packet. This PreToolUse hook sees that command plus the
# session_id (which the bare script cannot know) and writes the state; the
# script itself is a no-op carrier. Non-converged statuses (cap-reached,
# critical-blocker, plan-impact) run no mark, so the session stays dirty —
# fail-closed: a blocked commit costs one /review; an unblocked commit over
# outstanding findings is the failure this hook exists to prevent.
#
# A command containing `git commit` is never processed as a mark — the block
# check runs first and exits, so `review-gate-mark clean && git commit` cannot
# self-authorize in a single command.
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
      coder|coder-deep|backend-coder|backend-coder-deep|frontend-coder|frontend-coder-deep|review-loop)
        echo dirty > "$state_file" ;;
    esac
    ;;
  PreToolUse)
    cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
    if grep -qE '\bgit\s+commit\b' <<<"$cmd"; then
      [[ -f "$state_file" && "$(cat "$state_file")" == "dirty" ]] || exit 0
      if [[ -f "$skip_file" ]]; then
        rm -f "$skip_file"
        exit 0
      fi
      echo "[review-commit-gate] A coder or review-loop dispatch ran this session and no converged review has been recorded since. Run /review — its wrapper records convergence via review-gate-mark. Only if the USER explicitly approved skipping review for a trivial diff, create the one-shot override and retry: touch $skip_file — never create it on your own judgment." >&2
      exit 2
    fi
    if grep -qE 'review-gate-mark[[:space:]]+(clean|dirty)\b' <<<"$cmd"; then
      mark=$(grep -oE 'review-gate-mark[[:space:]]+(clean|dirty)' <<<"$cmd" | awk '{print $2}' | head -1)
      echo "$mark" > "$state_file"
    fi
    ;;
esac
exit 0
