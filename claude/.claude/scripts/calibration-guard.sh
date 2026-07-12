#!/usr/bin/env bash
# calibration-guard.sh — SessionStart hook.
#
# /calibrate seeds a real defect into a real file to measure reviewer recall.
# It always restores — unless the session died mid-run. That would leave a
# deliberately-broken file in the working tree looking like ordinary work.
#
# The lock file is written before the mutation and deleted only after the
# restore is hash-verified. If it survives into a new session, the restore
# never happened: say so immediately, with the paths needed to fix it.
set -euo pipefail

lock="$HOME/.claude/calibration-lock.json"
[[ -f "$lock" ]] || exit 0
command -v jq >/dev/null || exit 0

file=$(jq -r '.file // "?"' "$lock" 2>/dev/null || echo '?')
backup=$(jq -r '.backup_path // "?"' "$lock" 2>/dev/null || echo '?')
class=$(jq -r '.class // "?"' "$lock" 2>/dev/null || echo '?')
ts=$(jq -r '.ts // "?"' "$lock" 2>/dev/null || echo '?')

cat <<EOF
⚠️  UNRESTORED CALIBRATION SEED — a previous /calibrate run did not finish.

A deliberate '$class' defect was seeded at $ts and may still be in:
  $file

Restore it from the backup before doing ANY other work in that repo:
  cp "$backup" "$file"

Then verify the diff is back to what you expect and remove the lock:
  rm "$lock"

Do not commit until this is resolved.
EOF
exit 0
