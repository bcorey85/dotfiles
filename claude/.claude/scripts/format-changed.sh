#!/usr/bin/env bash
# format-changed.sh — format only the files a turn changed, once, at turn end.
# UserPromptSubmit snapshots the dirty set with content hashes; Stop formats
# files new to that set or whose hash moved, so untouched hand edits are left
# alone. Silent and always exits 0: UserPromptSubmit stdout becomes context,
# and a blocking Stop hook re-invokes the model.
set -uo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
command -v jq >/dev/null || exit 0

input=$(cat)
evt=$(jq -r '.hook_event_name // ""' <<<"$input" 2>/dev/null) || exit 0
session=$(jq -r '.session_id // ""' <<<"$input" 2>/dev/null) || exit 0
cwd=$(jq -r '.cwd // ""' <<<"$input" 2>/dev/null) || exit 0
[[ -z "$session" ]] && exit 0
[[ -z "$cwd" ]] && cwd=$PWD

root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

state_dir="$HOME/.claude/state/format-changed"
mkdir -p "$state_dir" 2>/dev/null || exit 0
find "$state_dir" -type f -mtime +2 -delete 2>/dev/null || true
snap="$state_dir/$session-$(printf '%s' "$root" | cksum | awk '{print $1}')"

# "<hash> <path>" for every existing file in the dirty set.
dirty_hashes() {
  local existing=() f
  while IFS= read -r f; do
    [[ -f "$f" ]] && existing+=("$f")
  done < <({ git diff --name-only --diff-filter=d HEAD; git ls-files --others --exclude-standard; } 2>/dev/null | sort -u)
  (( ${#existing[@]} )) || return 0
  paste -d' ' <(git hash-object -- "${existing[@]}") <(printf '%s\n' "${existing[@]}")
}

case "$evt" in
  UserPromptSubmit)
    dirty_hashes > "$snap" 2>/dev/null
    exit 0 ;;
  Stop) ;;
  *) exit 0 ;;
esac

[[ -f "$snap" ]] || exit 0

fmt=()
lint=()
while IFS= read -r f; do
  case "$f" in
    *.ts|*.tsx|*.js|*.jsx|*.vue) fmt+=("$f"); lint+=("$f") ;;
    *.json|*.css|*.scss|*.md)    fmt+=("$f") ;;
  esac
done < <(dirty_hashes | grep -vxFf "$snap" | cut -d' ' -f2-)
(( ${#fmt[@]} )) || exit 0

if (( ${#lint[@]} )); then
  if command -v oxlint &>/dev/null || [[ -x node_modules/.bin/oxlint ]]; then
    npx oxlint --fix "${lint[@]}" >/dev/null 2>&1
  elif [[ -x node_modules/.bin/eslint ]]; then
    npx eslint --fix --no-warn-ignored --max-warnings=0 "${lint[@]}" >/dev/null 2>&1
  fi
fi

if command -v oxfmt &>/dev/null || [[ -x node_modules/.bin/oxfmt ]]; then
  npx oxfmt "${fmt[@]}" >/dev/null 2>&1
else
  # No local prettier on any of the four platforms — npx fetches it on demand.
  npx --yes prettier --write "${fmt[@]}" >/dev/null 2>&1
fi

exit 0
