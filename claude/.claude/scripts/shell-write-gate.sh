#!/usr/bin/env bash
# shell-write-gate.sh — PreToolUse(Bash): deny shell writes that bypass the
# Write/Edit hook pipeline.
#   0. Test ownership (any agent_type): every path a command writes, moves,
#      copies or deletes goes through test-ownership-gate.sh. Not escapable.
#   1. In-place editors (sed -i, perl -pi, awk -i inplace), any target.
#   2. Redirection (>, >>) and tee onto a git-tracked file.
# Escape for rules 1–2: a trailing `#skip-shell-write-gate` comment (an env
# prefix never reaches a PreToolUse hook). Fails closed; open without jq.
set -Eeuo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

emitted=0
deny() {
  emitted=1
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
fail_closed() {
  local rc=$?
  if (( rc != 0 && emitted == 0 )); then
    deny "[shell-write-gate] internal error (exit $rc) — failing closed. Report this to the user."
  fi
  return 0
}
trap fail_closed EXIT

command -v jq >/dev/null || exit 0
input=$(cat)
cmd=$(jq -r '.tool_input.command // ""' <<<"$input" 2>/dev/null) || deny "[shell-write-gate] hook input did not parse — failing closed. Report this to the user."
agent=$(jq -r '.agent_type // ""' <<<"$input")
cwd=$(jq -r '.cwd // ""' <<<"$input")
[[ -z "$cwd" ]] && cwd=$PWD
if [[ -z "$cmd" ]]; then exit 0; fi

trim() {
  local s=$1
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

unquote() {
  local s=$1
  s=${s%\"}; s=${s#\"}
  s=${s%\'}; s=${s#\'}
  printf '%s' "$s"
}

is_inplace() {
  case "$1" in
    sed|gsed) grep -qE '(^|[[:space:]])(-[a-zA-Z]*i|--in-place([[:space:]=]|$))' <<<"$2" ;;
    perl)
      grep -qE '(^|[[:space:]])-[a-zA-Z]*i' <<<"$2" \
        && grep -qE '(^|[[:space:]])-[a-zA-Z]*[pn]' <<<"$2" ;;
    awk|gawk) grep -qE '(^|[[:space:]])-i[[:space:]]*inplace' <<<"$2" ;;
    *) return 1 ;;
  esac
}

# Index of the first word past leading time / env / VAR=val wrappers.
cmd_word_index() {
  local -a words
  read -ra words <<<"$1" || true
  local i=0
  while [[ "${words[i]:-}" =~ ^(time|env|[A-Za-z_][A-Za-z0-9_]*=.*)$ ]]; do i=$((i + 1)); done
  printf '%s' "$i"
}

seg_cmd_word() {
  local -a words
  read -ra words <<<"$1" || true
  local i
  i=$(cmd_word_index "$1")
  local word=${words[i]:-}
  printf '%s' "${word##*/}"
}

# Editor word in a command position: the segment's own command word, or one
# handed to an invoker (`xargs sed -i`, `find -exec sed -i`). An editor name
# that is merely an argument (`grep -in sed`) is not a command.
find_editor_word() {
  local -a words
  read -ra words <<<"$1" || true
  local w b invoked=0 idx=0 cmdi
  cmdi=$(cmd_word_index "$1")
  for w in "${words[@]}"; do
    b=${w##*/}
    case "$b" in
      sed|gsed|perl|awk|gawk)
        if (( idx == cmdi || invoked )); then printf '%s' "$b"; return 0; fi ;;
      xargs|-exec|-execdir|sh|bash|zsh|-c|sudo|nice|timeout|parallel) invoked=1 ;;
    esac
    idx=$((idx + 1))
  done
  return 1
}

# Absolute path for a target; non-zero for empty, -*, &* and /dev/*.
resolve_target() {
  local p
  p=$(unquote "$(trim "$1")")
  [[ -z "$p" || "$p" == -* || "$p" == \&* || "$p" == /dev/* ]] && return 1
  [[ "$p" == "~"* ]] && p="$HOME${p#\~}"
  [[ "$p" != /* ]] && p="$cwd/$p"
  printf '%s' "$p"
}

nl=$'\n'
segments=${cmd//||/$nl}
segments=${segments//&&/$nl}
segments=${segments//[|;]/$nl}

targets=$(
  {
    grep -oE '>>?[[:space:]]*[^[:space:]|&;<>()]+' <<<"$cmd" | sed -E 's/^>>?[[:space:]]*//'
    grep -oE '(^|[[:space:]])tee([[:space:]]+-[a-zA-Z-]+)*[[:space:]]+[^[:space:]|&;<>()]+' <<<"$cmd" \
      | sed -E 's/^[[:space:]]*tee([[:space:]]+-[a-zA-Z-]+)*[[:space:]]+//'
  } || true
)

ownership_gate="$(dirname -- "${BASH_SOURCE[0]}")/test-ownership-gate.sh"

check_ownership() {
  local p
  p=$(resolve_target "$1") || return 0
  local target out
  # The trailing-slash form lets a bare test directory match `*/tests/*`.
  for target in "$p" "${p%/}/"; do
    out=$(jq -cn --arg a "$agent" --arg f "$target" '{agent_type:$a, tool_input:{file_path:$f}}' | bash "$ownership_gate")
    if [[ -n "$out" ]]; then
      deny "[shell-write-gate] $(jq -r '.hookSpecificOutput.permissionDecisionReason' <<<"$out")"
    fi
  done
  return 0
}

if [[ -n "$agent" && -f "$ownership_gate" ]]; then
  while IFS= read -r t; do check_ownership "$t"; done <<<"$targets"

  while IFS= read -r seg; do
    read -ra words <<<"$seg" || true
    (( ${#words[@]} )) || continue
    i=$(cmd_word_index "$seg")
    word=${words[i]:-}
    word=${word##*/}
    editor_word=$(find_editor_word "$seg") || editor_word=""
    case "$word" in
      sed|gsed|perl|awk|gawk) is_inplace "$word" "$seg" || continue ;;
      rm|unlink|mv|cp|install|truncate|touch|ln|dd|patch) ;;
      git)
        [[ "${words[i+1]:-}" =~ ^(rm|mv|checkout|restore|apply)$ ]] || continue
        i=$((i + 1)) ;;
      *)
        [[ -n "$editor_word" ]] && is_inplace "$editor_word" "$seg" || continue ;;
    esac
    for w in "${words[@]:i+1}"; do
      [[ "$word" == dd ]] && w=${w#of=}
      check_ownership "$w"
    done
  done <<<"$segments"
fi

if grep -qF '#skip-shell-write-gate' <<<"$cmd"; then exit 0; fi

if ! grep -qE '(-[a-zA-Z]*i|inplace|>|tee)' <<<"$cmd"; then exit 0; fi

escape_hint=" If this deny is wrong (a > inside a quoted string or heredoc, an unrecognized wrapper), re-run the command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command."

while IFS= read -r seg; do
  seg=$(trim "$seg")
  [[ -z "$seg" ]] && continue

  word=$(find_editor_word "$seg") || continue
  is_inplace "$word" "$seg" || continue

  target=${seg##*[[:space:]]}
  if [[ -z "$target" || "$target" == -* || "$target" == *\'* || "$target" == *\"* || "$target" == "$word" ]]; then
    target=$seg
  fi
  deny "[shell-write-gate] in-place editing of $target bypasses the Write/Edit hook pipeline. Use the Write or Edit tool.$escape_hint"
done <<<"$segments"

while IFS= read -r t; do
  t=$(resolve_target "$t") || continue

  if [[ -L "$t" ]]; then
    resolved=$(readlink -f -- "$t" 2>/dev/null) && [[ -n "$resolved" ]] && t=$resolved
  fi

  if git -C "$(dirname -- "$t")" ls-files --error-unmatch -- "$(basename -- "$t")" >/dev/null 2>&1; then
    deny "[shell-write-gate] $t is git-tracked. Shell writes bypass the Write/Edit hook pipeline (comment/prose/budget gates). Use the Write or Edit tool.$escape_hint"
  fi
done <<<"$targets"

exit 0
