#!/usr/bin/env bash
# log-skill-use.sh — skill-usage telemetry for /skill-audit.
#
# Registered for two hook events in settings.json:
#   PostToolUse (matcher: Skill)  — model-invoked skills via the Skill tool
#   UserPromptSubmit              — user-typed /slash invocations
#
# Appends {ts, skill, via, repo} to ~/.claude/skill-usage.jsonl. Never blocks:
# always exits 0, emits no hook output. User-typed built-in commands (/clear,
# /model, ...) land in the log too; /skill-audit filters against the skills dir.
set -euo pipefail

command -v jq >/dev/null || exit 0
input=$(cat)

evt=$(jq -r '.hook_event_name // ""' <<<"$input")
skill=""
via=""

case "$evt" in
  PostToolUse)
    skill=$(jq -r '.tool_input.skill // ""' <<<"$input")
    via="model"
    ;;
  UserPromptSubmit)
    prompt=$(jq -r '.prompt // ""' <<<"$input")
    if [[ "$prompt" =~ ^/([A-Za-z0-9:_-]+) ]]; then
      skill="${BASH_REMATCH[1]}"
      via="user"
    fi
    ;;
esac

[[ -z "$skill" ]] && exit 0

repo=$(basename "${CLAUDE_PROJECT_DIR:-$PWD}")
out="${SKILL_USAGE_FILE:-$HOME/.claude/skill-usage.jsonl}"

jq -cn --arg skill "$skill" --arg via "$via" --arg repo "$repo" \
  '{ts: (now | todate), skill: $skill, via: $via, repo: $repo}' >> "$out" 2>/dev/null || true

exit 0
