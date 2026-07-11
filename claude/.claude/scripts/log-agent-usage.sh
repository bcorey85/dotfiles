#!/usr/bin/env bash
# log-agent-usage.sh — per-dispatch token telemetry for /audit review.
#
# Registered in settings.json: PostToolUse (matcher: Agent). Appends one line
# per completed subagent dispatch to ~/.claude/agent-usage.jsonl:
#   {ts, repo, agent, model, desc, tokens, toolUses, durationMs, respKeys}
#
# The token fields probe several candidate paths because the Agent
# tool_response schema is not contractual across CLI versions; respKeys is the
# self-diagnostic — if tokens comes back null, look there for the real field
# name and add it to the fallback chain. Never blocks: always exits 0.
set -euo pipefail

command -v jq >/dev/null || exit 0
input=$(cat)

evt=$(jq -r '.hook_event_name // ""' <<<"$input")
[[ "$evt" == "PostToolUse" ]] || exit 0

repo=$(basename "${CLAUDE_PROJECT_DIR:-$PWD}")
out="${AGENT_USAGE_FILE:-$HOME/.claude/agent-usage.jsonl}"

jq -c --arg repo "$repo" '
(.tool_response | if type == "object" then . else {} end) as $r |
{
  ts: (now | todate),
  repo: $repo,
  agent: (.tool_input.subagent_type // "general-purpose"),
  model: (.tool_input.model // "inherit"),
  desc: ((.tool_input.description // "") | .[0:80]),
  tokens: ($r.totalTokens // $r.usage.total_tokens
           // $r.total_tokens // $r.usage.output_tokens // null),
  toolUses: ($r.totalToolUseCount // $r.tool_uses // null),
  durationMs: ($r.totalDurationMs // $r.duration_ms // null),
  respKeys: ((.tool_response | keys?) // (.tool_response | type))
}' <<<"$input" >> "$out" 2>/dev/null || true

exit 0
