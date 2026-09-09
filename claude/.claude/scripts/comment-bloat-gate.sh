#!/usr/bin/env bash
# PostToolUse hook: block workflow-marker leaks and comment bloat in committed code.
# Enforces coder-core's density cap and _shared/code-vocabulary.md deterministically.
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0
echo "$FILE" | grep -qE '\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|php|c|h|cc|cpp|hpp|lua|qml|sh|bash|zsh)$' || exit 0
# Agent/skill/hook surfaces have their own gates and carry header prose by design.
# A repo checked out under .claude/worktrees/ is ordinary code, so the worktree
# prefix is stripped before the exemption is tested.
SURFACE=$FILE
case "$FILE" in
  */.claude/worktrees/*|.claude/worktrees/*)
    SURFACE=${FILE#*.claude/worktrees/}
    SURFACE=${SURFACE#*/}
    ;;
esac
case "/$SURFACE" in */.claude/*) exit 0 ;; esac

NEW=$(echo "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // empty')
[ -z "$NEW" ] && exit 0

# The bare `*` alternative is a JSDoc continuation line, so it requires a space or
# line end after it — `**unpacking` and `*args` are code.
CRE='^[[:space:]]*(//|#|\*([[:space:]]|$)|--|;|/\*|"""|<!--)'

# Numbered against the file, not the comment-only stream, so the reported line is
# the real one. Uppercase-anchored markers (ticket keys, decision and criterion
# ids) match case-sensitively — under -i they hit ordinary lowercase prose.
MARKED=$( { CAND=$(grep -nE "$CRE" "$FILE")
  printf '%s\n' "$CAND" | grep -Ei \
    -e '\bphases?[[:space:]]*[0-9]' \
    -e 'docs/plans/' \
    -e '\b(PR|issue)[[:space:]]*#[0-9]+' \
    -e 'per the (architect|plan|spec|ledger)' \
    -e 'written by the (coder|architect|poller|assistant|agent)' \
    -e 'decision ledger|acceptance criteri|acceptance contract' \
    -e 'plan[ -]?impact'
  printf '%s\n' "$CAND" | grep -E \
    -e '\(D[0-9]+[):]' \
    -e '\bD[0-9]+:' \
    -e '\bAC[0-9]+\b' \
    -e '\b[A-Z]{2,6}-[0-9]{1,5}\b'
  } | grep -viE 'utf-8|sha-[0-9]|iso-[0-9]|rfc-[0-9]|aes-[0-9]|http-[0-9]|base-[0-9]' \
    | sort -t: -k1,1n -u)

# Only lines this edit contributed are charged.
LEAKS=""
if [ -n "$MARKED" ]; then
  while IFS= read -r row; do
    printf '%s\n' "$NEW" | grep -qxF "${row#*:}" && LEAKS="${LEAKS}${row}"$'\n'
  done <<< "$MARKED"
fi

if [ -n "$LEAKS" ]; then
  echo "comment-bloat-gate: private-workflow marker in a code comment ($(basename "$FILE")). Zero exceptions — keep the reason, drop the pointer (_shared/code-vocabulary.md):" >&2
  printf '%s' "$LEAKS" | sed 's/^/  /' >&2
  exit 2
fi

# Density cap: fires only when THIS edit added comments and the file is over ~20%.
# Only true comment lines count — narration is the target. A bare docstring/JSDoc
# delimiter is structure, not prose, so it is not charged.
DELIM='^[[:space:]]*("""|'"'''"'|/\*\*?|\*/)[[:space:]]*$'
echo "$NEW" | grep -E "$CRE" | grep -qvE "$DELIM" || exit 0
TOTAL=$(grep -cE '[^[:space:]]' "$FILE")
[ "$TOTAL" -lt 30 ] && exit 0
CMT=$(grep -E "$CRE" "$FILE" | grep -cvE "$DELIM")
PCT=$(( CMT * 100 / TOTAL ))
if [ "$PCT" -gt 22 ]; then
  echo "comment-bloat-gate: $(basename "$FILE") is ${PCT}% comments (${CMT}/${TOTAL} non-blank lines), cap ~20%. Delete the comments this edit added, or rename/split so they are unnecessary. Never add code to lower the ratio." >&2
  exit 2
fi
exit 0
