#!/usr/bin/env bash
set -euo pipefail
# UserPromptSubmit hook: Scan prompt for secrets before sending
trap 'printf '"'"'{"decision":"block","reason":"prompt-secrets encountered an unexpected error — blocking for safety"}\n'"'"'; exit 0' ERR

temp_file=""

if ! command -v sonar &> /dev/null; then
  exit 0
fi

# Read JSON from stdin
stdin_data=$(cat)

# Parse prompt: try jq, python3, then sed
if command -v jq &>/dev/null; then
    prompt=$(printf '%s' "$stdin_data" | jq -r '.prompt // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    prompt=$(printf '%s' "$stdin_data" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt',''))" 2>/dev/null)
else
    prompt=$(printf '%s' "$stdin_data" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

if [[ -z "$prompt" ]]; then
  exit 0
fi

# Create temporary file with prompt content (stdin is already occupied by hook input)
temp_file=$(mktemp -t 'sonarqube-cli-hook.XXXXXX')
trap 'rm -f "$temp_file"' EXIT

printf '%s' "$prompt" > "$temp_file"

# Scan prompt for secrets (using file instead of stdin pipe)
sonar analyze secrets "$temp_file" > /dev/null 2>&1 || exit_code=$?
exit_code=${exit_code:-0}

if [[ $exit_code -eq 51 ]]; then
  # Secrets found - block prompt
  printf '{"decision":"block","reason":"Sonar detected secrets in prompt"}\n'
  exit 0
fi

exit 0
