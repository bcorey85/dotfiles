#!/usr/bin/env bash
set -euo pipefail
# PreToolUse hook: Scan files before reading to prevent secret leakage
# Blocks file reads if secrets are detected
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"pretool-secrets encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR

if ! command -v sonar &> /dev/null; then
  exit 0
fi

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    exit 0
}

# Read JSON from stdin
stdin_data=$(cat)

# Parse tool_name: try jq, python3, then sed
if command -v jq &>/dev/null; then
    tool_name=$(printf '%s' "$stdin_data" | jq -r '.tool_name // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    tool_name=$(printf '%s' "$stdin_data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
else
    tool_name=$(printf '%s' "$stdin_data" | sed -n 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

if [[ "$tool_name" != "Read" ]]; then
  exit 0
fi

# Parse file_path: try jq, python3, then sed
if command -v jq &>/dev/null; then
    file_path=$(printf '%s' "$stdin_data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    file_path=$(printf '%s' "$stdin_data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
else
    file_path=$(printf '%s' "$stdin_data" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

if [[ -z "$file_path" ]]; then
  block "Could not parse file path from hook input — denying for safety"
fi

if [[ ! -f "$file_path" ]]; then
  exit 0
fi

# Scan file for secrets
sonar analyze secrets "$file_path" > /dev/null 2>&1 || exit_code=$?
exit_code=${exit_code:-0}

if [[ $exit_code -eq 51 ]]; then
  # Secrets found - deny file read
  block "Sonar detected secrets in file: $file_path"
fi

exit 0
