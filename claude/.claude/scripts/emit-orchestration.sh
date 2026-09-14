#!/usr/bin/env bash
# emit-orchestration.sh — SessionStart: inject ~/.claude/orchestration.md as
# additionalContext. Main session only; subagents never see it.
set -euo pipefail
command -v jq >/dev/null || exit 0
f="$HOME/.claude/orchestration.md"
if [[ -r "$f" ]]; then
  jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' "$f"
else
  jq -cn '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:"WARNING: ~/.claude/orchestration.md is missing or unreadable. Workflow-routing rules are NOT loaded this session. Tell the user before routing any work."}}'
fi
