#!/usr/bin/env bash
# PostToolUse hook: run ESLint on JS/TS/Vue files after Write|Edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then exit 0; fi

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.vue)
    npx eslint --fix --no-warn-ignored --max-warnings=0 "$FILE" 2>/dev/null
    ;;
esac
