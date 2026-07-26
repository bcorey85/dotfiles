#!/usr/bin/env bash
# PostToolUse hook: run Prettier on supported files after Write|Edit
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then exit 0; fi

case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.vue|*.json|*.css|*.scss|*.md) ;;
  *) exit 0 ;;
esac

# Run from the file's OWN repo root, not the session's cwd.
#
# Prettier resolves .prettierignore relative to the process working directory,
# never relative to the file being formatted. This hook used to inherit whatever
# directory the agent session happened to sit in, so a repo's ignore rules were
# honored only by coincidence — which is how byte-faithful test fixtures get
# silently reformatted, replacing the thing under test with prettier's idea of
# the same document. No diff, no review surface (2>/dev/null eats the evidence).
#
# Side benefit: npx now resolves the repo's own prettier and config too.
DIR=$(dirname "$FILE")
ROOT=$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null) || ROOT=""
[ -n "$ROOT" ] || ROOT="$DIR"

cd "$ROOT" 2>/dev/null || exit 0
npx prettier --write "$FILE" 2>/dev/null || true
