#!/usr/bin/env bash
# calibration-refs-guard.sh — PostToolUse(Write|Edit) hook.
#
# The shared reviewer calibration file has five `##` headings that every reviewer
# agent names verbatim in its first-action line ("adopt its X, Y, Z"). The file
# says so in its own preamble. That warning is prose addressed to whoever edits
# next, and it does not fire: a heading was renamed, two of five agents were
# updated, and three shipped pointing at a section that no longer existed.
#
# This makes the warning a check. It runs only when the calibration file or one
# of the agents that reads it was just written, and it reports rather than
# blocks — a rename is legitimate work, and the point is that the other half of
# it does not get forgotten.
set -euo pipefail

# Overridable so the detecting case can be exercised against fixtures without
# breaking the live config to test the check.
calib="${CALIB_FILE:-$HOME/.claude/skills/_shared/reviewer-calibration.md}"
agents="${CALIB_AGENTS_DIR:-$HOME/.claude/agents}"

command -v jq >/dev/null || exit 0
path=$(jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
case "$path" in
  *reviewer-calibration.md | "$agents"/*reviewer*.md) ;;
  *) exit 0 ;;
esac

[[ -f "$calib" ]] || exit 0

missing=""
for f in "$agents"/*reviewer*.md; do
  [[ -f "$f" ]] || continue
  # First-action lines name each adopted section as **Bold Heading**.
  refs=$(grep -h 'reviewer-calibration\.md' "$f" | grep -o '\*\*[^*]*\*\*' | tr -d '*' || true)
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    grep -qiF "## $ref" "$calib" || missing+="  ${f##*/} names \"$ref\" — no such heading in the calibration file"$'\n'
  done <<<"$refs"
done

[[ -n "$missing" ]] || exit 0

cat <<EOF
⚠️  Reviewer calibration references are out of sync.

$missing
A reviewer told to adopt a heading that does not exist gets that section only by
accident, through "adopt in full". Update every agent that names the heading, or
restore the heading, before moving on.
EOF
exit 0
