#!/usr/bin/env bash
# PostToolUse hook: run Prettier on supported files after Write|Edit
FILE="$CLAUDE_FILE_PATH"
if [ -z "$FILE" ]; then exit 0; fi

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.vue|*.json|*.css|*.scss|*.md)
    npx prettier --write "$FILE" 2>/dev/null || true
    ;;
esac
