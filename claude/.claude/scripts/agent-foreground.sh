#!/usr/bin/env bash
# static-hooks/unix/agent-foreground.sh
# PreToolUse (matcher: Agent). Inside a subagent, force `run_in_background: false` on every
# Agent dispatch.
#
# Why: the Agent tool defaults to background. A subagent cannot wait on a background agent —
# the completion notice goes to the top-level session, and the subagent has no tool to block
# on the result. So a nested dispatch (review-loop -> code-reviewer) returns a launch stub and
# the caller never sees the review. Top-level dispatches are untouched: the main session
# receives completion notices and keeps its background agents.
#
# Logic:
#   1. CLAUDE_SKIP_HOOKS set to any non-empty value -> exit 0 (documented bypass).
#   2. Nested caller = hook input carries `agent_id` or `agent_type` (present only inside a
#      subagent call). Neither field -> exit 0, call runs unchanged.
#   3. Otherwise answer allow + updatedInput = the call's input plus run_in_background:false.
#   4. Never blocks: on any failure exit 0 with no output.
set -uo pipefail
[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
command -v jq >/dev/null || exit 0
input=$(cat)
[[ $(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null) == Agent ]] || exit 0
[[ -n $(jq -r '.agent_id // .agent_type // ""' <<<"$input" 2>/dev/null) ]] || exit 0
jq -c '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:(.tool_input + {run_in_background:false})}}' <<<"$input" 2>/dev/null || exit 0
