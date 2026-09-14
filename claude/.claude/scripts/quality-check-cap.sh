#!/usr/bin/env bash
# quality-check-cap.sh — cap a quality check at one re-run per edit.
# PostToolUse(Write|Edit|...) touches `edits`; PreToolUse(Bash) denies a check
# whose last run is newer than `edits`; PostToolUse and PostToolUseFailure
# (Bash) record the run, so a denied, rejected or abandoned attempt — an edit
# as much as a check — never moves either marker. Key: normalized
# command + effective cwd. Escape: a trailing `#skip-quality-cap`.
# Fails closed only on the PreToolUse Bash path; state errors fail open.
set -Eeuo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

tool=""
evt=""
emitted=0
deny() {
  emitted=1
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
fail_closed() {
  local rc=$?
  [[ "$tool" != Bash || "$evt" != PreToolUse ]] && return 0
  if (( rc != 0 && emitted == 0 )); then
    deny "[quality-check-cap] internal error (exit $rc) — failing closed. Report this to the user."
  fi
  return 0
}
trap fail_closed EXIT

command -v jq >/dev/null || exit 0
input=$(cat)
tool=$(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null) || exit 0
evt=$(jq -r '.hook_event_name // ""' <<<"$input")
session=$(jq -r '.session_id // "unknown"' <<<"$input")
cwd=$(jq -r '.cwd // ""' <<<"$input")
[[ -z "$cwd" ]] && cwd=$PWD

root="$HOME/.claude/state/quality-check"
dir="$root/$session"
mkdir -p "$dir" 2>/dev/null || exit 0
find "$root" -mindepth 1 -mtime +2 -delete 2>/dev/null || true

case "$tool" in
  Write|Edit|MultiEdit|NotebookEdit)
    touch "$dir/edits" 2>/dev/null || true
    exit 0 ;;
  Bash) ;;
  *) exit 0 ;;
esac

cmd=$(jq -r '.tool_input.command // ""' <<<"$input")
if [[ -z "$cmd" ]]; then exit 0; fi
if [[ "$evt" == PreToolUse ]] && grep -qF '#skip-quality-cap' <<<"$cmd"; then exit 0; fi
cmd=${cmd//#skip-quality-cap/}

checks='(npm|pnpm|yarn|bun)( run)? (test|lint|typecheck|type-check|check|build)|jest|vitest|pytest|tsc|eslint|ruff|mypy|go (test|vet)|golangci-lint|cargo (test|clippy|check)|make (test|lint|check|typecheck)|(bundle exec )?rspec|phpunit|dotnet test|mvn test|gradle test|shellcheck|luacheck|stylua'

nl=$'\n'
segments=${cmd//||/$nl}
segments=${segments//&&/$nl}
segments=${segments//[|;]/$nl}

while IFS= read -r seg; do
  seg=$(sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' <<<"$seg")
  if [[ "$seg" =~ ^cd[[:space:]]+([^[:space:]]+)$ ]]; then
    d=${BASH_REMATCH[1]}
    [[ "$d" == "~"* ]] && d="$HOME${d#\~}"
    [[ "$d" == /* ]] && cwd=$d || cwd="$cwd/$d"
    continue
  fi
  while :; do
    stripped=$(sed -E 's/^(time|env|npx|bunx|pnpm exec|yarn dlx)[[:space:]]+//; s/^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+//' <<<"$seg")
    [[ "$stripped" == "$seg" ]] && break
    seg=$stripped
  done
  grep -qE "^($checks)([[:space:]]|\$)" <<<"$seg" || continue

  norm=$(sed -E 's/[0-9]*>&[0-9]+//g; s/[0-9]*>>?[[:space:]]*[^[:space:]]+//g; s/[[:space:]]+/ /g; s/^ //; s/ $//' <<<"$seg")
  key=$(printf '%s\n%s' "$norm" "$cwd" | cksum | awk '{print $1}')

  if [[ "$evt" == PostToolUse || "$evt" == PostToolUseFailure ]]; then
    touch "$dir/run-$key" 2>/dev/null || exit 0
    continue
  fi

  if [[ "$dir/run-$key" -nt "$dir/edits" ]]; then
    deny "[quality-check-cap] '$norm' already ran this session and nothing has been edited since. Re-running unchanged code cannot produce a different result. Redirect the failing run to /tmp/check.log, read the WHOLE log, fix every failure in one batch, then run it once more. If it still fails after that batch fix, stop and ask the user. If this deny is wrong, re-run the command with a trailing #skip-quality-cap comment — it disarms this gate for that one command."
  fi
done <<<"$segments"

exit 0
