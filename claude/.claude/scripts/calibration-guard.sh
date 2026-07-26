#!/usr/bin/env bash
# calibration-guard.sh — SessionStart hook.
#
# Two things deliberately mutate a real file in the working tree:
#   /calibrate      — seeds a defect to measure REVIEWER recall
#   mutation-tester — applies a mutant to measure whether the TESTS kill it
#
# Both always restore — unless the session died mid-run. That would leave a
# deliberately-broken file in the working tree looking like ordinary work.
#
# They share ONE lock (distinguished by .kind) on purpose: neither may seed on
# top of the other's unrestored mutation, and a single lock makes that automatic.
# The lock is written before the mutation and deleted only after the restore is
# hash-verified. If it survives into a new session, the restore never happened:
# say so immediately, with the paths needed to fix it.
#
# The filename is historical — /calibrate was the first of the two. Renaming it
# would churn settings.json for no behavioral gain.
set -euo pipefail

lock="$HOME/.claude/calibration-lock.json"
[[ -f "$lock" ]] || exit 0
command -v jq >/dev/null || exit 0

file=$(jq -r '.file // "?"' "$lock" 2>/dev/null || echo '?')
backup=$(jq -r '.backup_path // "?"' "$lock" 2>/dev/null || echo '?')
class=$(jq -r '.class // "?"' "$lock" 2>/dev/null || echo '?')
ts=$(jq -r '.ts // "?"' "$lock" 2>/dev/null || echo '?')
kind=$(jq -r '.kind // "calibrate"' "$lock" 2>/dev/null || echo 'calibrate')

case "$kind" in
  mutation-test) what="MUTATION SEED — a previous mutation-tester run did not finish." ;;
  *)             what="CALIBRATION SEED — a previous /calibrate run did not finish." ;;
esac

cat <<EOF
⚠️  UNRESTORED $what

A deliberate '$class' mutation was applied at $ts and may still be in:
  $file

Restore it from the backup before doing ANY other work in that repo:
  cp "$backup" "$file"

Then verify the file is back to what you expect and remove the lock:
  rm "$lock"

Do not commit until this is resolved. Do not run /calibrate or dispatch
mutation-tester until this lock is gone — both refuse to seed on top of an
unrestored seed.
EOF
exit 0
