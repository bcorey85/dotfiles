#!/usr/bin/env bash
# static-hooks/unix/agent-model-guard.sh
# Guards Agent tool calls against silent Opus inheritance.
#
# Logic:
#   1. If CLAUDE_SKIP_HOOKS is set to any non-empty value, exit 0 immediately.
#      This keeps parity with other security hooks and lets the user bypass
#      all hooks consistently via the documented CLAUDE_SKIP_HOOKS mechanism.
#   2. Non-Agent tools pass immediately.
#   3. Call-site model containing "opus" (case-insensitive) is always blocked.
#      Opus subagents must be opted into via the agent file's own frontmatter,
#      never overridden from the call site.
#   4. Call-site model containing "inherit" (case-insensitive) is always blocked.
#      "inherit" resolves to the orchestrator's model at runtime — identical to
#      leaving model empty, but explicit. When the orchestrator is on Opus this
#      silently fans out Opus subagents.
#   5. Any other explicit model at the call site is allowed.
#   6. Empty model: resolve the agent file from CLAUDE_PROJECT_DIR (preferred)
#      or HOME, then check for a `model:` frontmatter line. If found, exit 0
#      (frontmatter handles selection, including a deliberate `model: opus`
#      pin). If not found, block — the subagent would silently inherit the
#      orchestrator's model, fanning out Opus when dispatched from an Opus
#      orchestrator.
#
# See ~/.claude/CLAUDE.md — Behavior § "Every `Agent` call MUST set `model` explicitly".

set -euo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

input="$(cat)"

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // ""')
if [[ "$tool_name" != "Agent" ]]; then
  exit 0
fi

model=$(printf '%s' "$input" | jq -r '.tool_input.model // ""')
subagent=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // ""')

if [[ -n "$subagent" ]] && [[ ! "$subagent" =~ ^[A-Za-z0-9_-]+$ ]]; then
  reason="Agent call to subagent_type='${subagent}' is invalid. subagent_type must contain only alphanumeric characters, hyphens, and underscores."
  jq -cn --arg r "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
  exit 0
fi

shopt -s nocasematch
if [[ "$model" == *opus* ]]; then
  shopt -u nocasematch
  {
    echo "[agent-model-guard] BLOCKED: Agent call sets model containing 'opus' at the call site."
    echo "Call-site Opus is forbidden. The only legitimate way to run a subagent on Opus"
    echo "is a 'model: opus' line in the agent file's own frontmatter."
    echo "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site."
  } >&2
  reason="Agent call sets model containing 'opus' at the call site. Call-site Opus is forbidden — add a 'model: opus' pin in the agent file frontmatter instead."
  jq -cn --arg r "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
  exit 0
fi
if [[ "$model" == *inherit* ]]; then
  shopt -u nocasematch
  {
    echo "[agent-model-guard] BLOCKED: Agent call sets model containing 'inherit' at the call site."
    echo "Call-site 'inherit' resolves to the orchestrator's model at runtime."
    echo "When the orchestrator is on Opus this silently fans out Opus subagents."
    echo "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site."
  } >&2
  reason="Agent call sets model containing 'inherit' at the call site. 'inherit' resolves to the orchestrator model at runtime, silently fanning out Opus subagents."
  jq -cn --arg r "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
  exit 0
fi
shopt -u nocasematch

if [[ -n "$model" ]]; then
  exit 0
fi

agent_file=""
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
  project_file="${CLAUDE_PROJECT_DIR}/.claude/agents/${subagent}.md"
  if [[ -f "$project_file" ]]; then
    agent_file="$project_file"
  fi
fi

if [[ -z "$agent_file" ]]; then
  home_file="${HOME}/.claude/agents/${subagent}.md"
  if [[ -f "$home_file" ]]; then
    agent_file="$home_file"
  fi
fi

if [[ -n "$agent_file" ]] && grep -q '^model:' "$agent_file"; then
  exit 0
fi

{
  echo "[agent-model-guard] BLOCKED: Agent call to subagent_type='${subagent}' has no model pin."
  echo "No 'model:' frontmatter was found in the agent file (or the agent file does not exist)."
  echo "Without a pin the subagent inherits the orchestrator's model — silently running Opus"
  echo "when dispatched from an Opus orchestrator."
  echo "Either:"
  echo "  - Add 'model: <opus|sonnet|haiku>' to the agent file's frontmatter, OR"
  echo "  - Pass an explicit model at the call site:"
  echo "      model: \"haiku\"  - read-only / lookup work"
  echo "      model: \"sonnet\" - fan-out implementation or analysis"
} >&2
reason="Agent call to subagent_type='${subagent}' has no model pin. No 'model:' frontmatter found in the agent file (or the file does not exist). Add a 'model:' line to the agent frontmatter or pass an explicit model at the call site."
jq -cn --arg r "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
exit 0
