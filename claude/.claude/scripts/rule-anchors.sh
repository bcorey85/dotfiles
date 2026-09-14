#!/usr/bin/env bash
# rule-anchors: a content hash per heading block of a prompt file, matched against
# docs/rule-anchors.md so every block has a recorded reason to exist.
#
#   rule-anchors.sh list <file>...   hash, file, heading: one line per block
#   rule-anchors.sh check            every file the sidecar names, against the sidecar
#
# A block is a heading line plus the text under it, up to the next heading outside a
# code fence. Whitespace runs collapse to one space before hashing, so a formatter's
# padding does not move a hash. File paths are relative to the .claude directory.
set -uo pipefail
CLAUDE_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SIDECAR="${RULE_ANCHORS:-$CLAUDE_DIR/../../docs/rule-anchors.md}"

blocks() { # <file> -> hash TAB heading
  awk '
    function flush() { if (body != "") { gsub(/[[:space:]]+/, " ", body); print (h == "" ? "(preamble)" : h) "\t" body } body = "" }
    /^```/ { fence = !fence }
    !fence && /^#{1,6} / { flush(); h = $0 }
    { body = body $0 " " }
    END { flush() }
  ' "$1" | while IFS=$'\t' read -r h body; do
    printf '%s\t%s\n' "$(printf '%s' "$body" | sha256sum | cut -c1-8)" "$h"
  done
}

case "${1:-}" in
  list)
    shift
    for f in "$@"; do
      rel="${f#"$CLAUDE_DIR"/}"
      rel="${rel#"$HOME"/.claude/}"
      blocks "$f" | awk -F'\t' -v f="$rel" '{ print $1 "\t" f "\t" $2 }'
    done ;;
  check)
    [[ -f "$SIDECAR" ]] || { echo "no sidecar at $SIDECAR"; exit 1; }
    rows=$(awk -F'|' '$2 ~ /^ *[0-9a-f]+ *$/ { gsub(/ /, "", $2); gsub(/^ +| +$/, "", $3); gsub(/^ +| +$/, "", $4); print $2 "\t" $3 "\t" $4 }' "$SIDECAR")
    status=0
    for rel in $(cut -f2 <<<"$rows" | sort -u); do
      [[ -f "$CLAUDE_DIR/$rel" ]] || { echo "MISSING FILE  $rel"; status=1; continue; }
      current=$(blocks "$CLAUDE_DIR/$rel")
      anchored=$(awk -F'\t' -v f="$rel" '$2 == f' <<<"$rows")
      while IFS=$'\t' read -r hash heading; do
        [[ -n "$hash" ]] || continue
        grep -q "^$hash"$'\t' <<<"$anchored" || { echo "UNANCHORED  $rel  $hash  $heading"; status=1; }
      done <<<"$current"
      while IFS=$'\t' read -r hash _ section; do
        [[ -n "$hash" ]] || continue
        grep -q "^$hash"$'\t' <<<"$current" || { echo "STALE  $rel  $hash  $section"; status=1; }
      done <<<"$anchored"
    done
    exit $status ;;
  *) sed -n '2,10p' "$0"; exit 2 ;;
esac
