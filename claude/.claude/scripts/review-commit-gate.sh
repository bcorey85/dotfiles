#!/usr/bin/env bash
# review-commit-gate.sh — mechanizes the global-CLAUDE.md rule "a coder
# dispatch obligates /review before /commit". The prose version of this rule
# needed three restatements and still leaked; this hook makes it deterministic.
#
# Contract (shared with omp's claude-security-bridge.ts): hook JSON on stdin,
# a single-line `permissionDecision` JSON verdict on stdout, exit 0.
#
# Registered twice in settings.json:
#   PostToolUse (matcher: Agent) — ARMS the gate:
#       coder* dispatch      -> "dirty" (unreviewed coder work exists)
#   PreToolUse  (matcher: Bash)  — two jobs:
#       blocks `git commit` while state is dirty
#       records `review-gate-mark clean|skip` — the ONLY clean transitions
#
# review-loop dispatch deliberately does NOT arm. It only ever runs after a
# coder that already armed, so arming on it bought nothing while stranding
# standalone /review sessions (no coder ran, nothing to gate) as dirty.
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
#   bash ~/.claude/scripts/review-gate-mark skip
#
# THE HUMAN MUST RUN THIS, NOT THE MODEL — and not by convention: the auto-mode
# classifier denies it from the agent regardless of how it is spelled. The old
# override was a bare `touch` into ~/.claude/state/; replacing it with a mark
# verb did NOT make it agent-reachable, because the classifier matches intent,
# not path. Treat skip as a human-only capability and word the block message so
# the model ASKS rather than attempts. (`clean` is not classifier-blocked, so
# the weaker claim is the harder one to make — deliberate, if surprising.)
#
# The self-authorization guard is unaffected: the `git commit` block check runs
# first and exits, so `review-gate-mark skip && git commit` still cannot work
# in a single command.
# fail_closed returns early on PostToolUse: that event has no deny semantics
# and a PreToolUse-shaped decision must never be emitted there. evt is declared
# before the parse, so a failure during `input=$(cat)` on a PostToolUse
# invocation still takes the deny branch — harmless, PostToolUse ignores
# permissionDecision and the exit is 0.
set -Eeuo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

emitted=0
evt=""
deny() {
  emitted=1
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
fail_closed() {
  local rc=$?
  [[ "$evt" == PostToolUse ]] && return 0
  if (( rc != 0 && emitted == 0 )); then
    deny "[review-commit-gate] internal error (exit $rc) — failing closed. Report this to the user."
  fi
  return 0
}
trap fail_closed EXIT

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
      deny "[review-commit-gate] Unreviewed coder work this session. Most common cause: a review DID converge and the mark was missed — if so, record it now: bash ~/.claude/scripts/review-gate-mark clean. Otherwise run /review. To skip review on a trivial diff, ASK THE USER to run 'bash ~/.claude/scripts/review-gate-mark skip' themselves and then retry — do not attempt it yourself, the classifier denies it from you by design."
    fi
    if grep -qE 'review-gate-mark[[:space:]]+(clean|dirty|skip)\b' <<<"$cmd"; then
      mark=$(grep -oE 'review-gate-mark[[:space:]]+(clean|dirty|skip)' <<<"$cmd" | awk '{print $2}' | head -1)
      if [[ "$mark" == skip ]]; then
        : > "$skip_file"
      else
        echo "$mark" > "$state_file"
      fi
    fi
    ;;
esac
exit 0
