#!/usr/bin/env bash
# PostToolUse hook: run ESLint on JS/TS/Vue files after Write|Edit
FILE="$CLAUDE_FILE_PATH"
if [ -z "$FILE" ]; then exit 0; fi

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.vue)
    npx eslint --fix --no-warn-ignored --max-warnings=0 "$FILE" 2>/dev/null
    ;;
esac
