#!/usr/bin/env bash
# PostToolUse hook: warn if CLAUDE.md exceeds 150 lines
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then exit 0; fi

if echo "$FILE" | grep -qiE 'CLAUDE\.md$'; then
    LINES=$(wc -l < "$FILE" 2>/dev/null || echo 0)
    if [ "$LINES" -gt 150 ]; then
        echo "CLAUDE.md is $LINES lines (target: <150). Consider moving reference data to skills or MEMORY.md." >&2
    fi
fi
