#!/usr/bin/env bash
# PreToolUse hook: test-edit-telemetry — LOG-ONLY, never blocks.
#
# Why this exists (LOOP-COST round 5): under an explicit prose prohibition,
# coder dispatches still Edit/Wrote test files 25 times across 4 arms. PreToolUse
# input carries no agent identity (anthropics/claude-code#40140), so a targeted
# deny ("coders may not edit assertions") is not mechanizable — but the telemetry
# is. This appends one JSONL line per Write/Edit touching a test file so the
# question "who edits tests, how often, in what repos" has data instead of grep
# archaeology when a future round wants the deny hook.
#
# Contract (matches the other gates): hook JSON on stdin; empty output = allow.
# This hook NEVER emits a permissionDecision and always exits 0.
#
# Log: ~/.claude/test-edit-telemetry.jsonl
#   {ts, tool, file, cwd, snippet} — snippet is the first 200 chars of
#   new_string/content, enough to classify mechanical-vs-assertion edits later.

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0

INPUT=$(cat)
[ -z "$INPUT" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

case "$FILE" in
  *_test.go|*.test.ts|*.test.tsx|*.test.js|*.test.jsx|*_spec.rb|*/test_*.py|*/tests/*.py|*.spec.ts|*.spec.js) ;;
  *) exit 0 ;;
esac

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf unknown)
printf '%s' "$INPUT" \
  | jq -c --arg ts "$TS" --arg tool "$TOOL" --arg file "$FILE" --arg cwd "${PWD:-}" \
      '{ts:$ts, tool:$tool, file:$file, cwd:$cwd,
        snippet: ((.tool_input.new_string // .tool_input.content // "")[:200])}' \
  >> "$HOME/.claude/test-edit-telemetry.jsonl" 2>/dev/null || true

exit 0
