#!/usr/bin/env bash
# PostToolUse hook: lint + format JS/TS/Vue files after Write|Edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then exit 0; fi

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.vue) ;;
  *) exit 0 ;;
esac

DIR=$(dirname "$FILE")
# Walk up to find the project root (nearest package.json)
ROOT="$DIR"
while [ "$ROOT" != "/" ]; do
  [ -f "$ROOT/package.json" ] && break
  ROOT=$(dirname "$ROOT")
done

# Lint: prefer oxlint, fall back to eslint
if command -v oxlint &>/dev/null || [ -f "$ROOT/node_modules/.bin/oxlint" ]; then
  npx oxlint --fix "$FILE" 2>/dev/null
elif [ -f "$ROOT/node_modules/.bin/eslint" ]; then
  npx eslint --fix --no-warn-ignored --max-warnings=0 "$FILE" 2>/dev/null
fi

# Format: prefer oxfmt, fall back to prettier
if command -v oxfmt &>/dev/null || [ -f "$ROOT/node_modules/.bin/oxfmt" ]; then
  npx oxfmt "$FILE" 2>/dev/null
elif [ -f "$ROOT/node_modules/.bin/prettier" ]; then
  npx prettier --write "$FILE" 2>/dev/null
fi
