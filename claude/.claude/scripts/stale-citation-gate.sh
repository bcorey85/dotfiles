#!/usr/bin/env bash
# PostToolUse: WARN on planning vocabulary in shipped source, and on document
# citations that no longer resolve. Both are grep-decidable; reviewer judgment
# leaks them. Never blocks — a human triages each hit.
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0

ROOT=$(git -C "$(dirname "$FILE")" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$ROOT" ] || exit 0
case "$FILE" in
  */.claude/*|*/node_modules/*|*/.venv/*|*/dist/*|*/build/*|*.min.js|*.lock) exit 0 ;;
esac
REL=${FILE#"$ROOT"/}

case "$FILE" in
  *.md|*.markdown|*.rst|*.txt)
    # Longest extension first: .jsonl must not match as .json, .tsv as .ts.
    CITES=$(grep -oE '\b[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_.-]+)+\.(markdown|jsonl|json|yaml|yml|tsx|tsv|toml|mjs|cjs|sql|sh|rs|py|md|ts|js|go)(:[0-9]{1,6})?([^A-Za-z0-9]|$)' "$FILE" 2>/dev/null | sed 's/[^A-Za-z0-9]$//' | sort -u)
    DOCDIR=$(dirname "$FILE")
    # A plan names files it will create; absence there is the point, not a defect.
    PROPOSES=0
    case "$REL" in */plans/*|*/spec.md|*-plan.md|*/PREREG*|*/plans-final/*) PROPOSES=1 ;; esac
    MISSING=""
    while IFS= read -r cite; do
      [ -z "$cite" ] && continue
      path=${cite%:*}; line=""
      case "$cite" in *.*:[0-9]*) line=${cite##*:} ;; *) path=$cite ;; esac
      case "$path" in *'<'*|*'*'*|*N.*|*'{'*) continue ;; esac
      target=""
      for cand in "$ROOT/$path" "$DOCDIR/$path"; do
        [ -e "$cand" ] && { target=$cand; break; }
      done
      if [ -z "$target" ]; then
        # A path whose own directory is absent is probably not repo-relative —
        # another repo, another root. Only a gap INSIDE a real directory is a
        # citation this tree falsified.
        anchored=0
        for cand in "$ROOT/$path" "$DOCDIR/$path"; do
          [ -d "$(dirname "$cand")" ] && anchored=1
        done
        if [ "$anchored" = 1 ] && { [ "$PROPOSES" = 0 ] || [ -n "$line" ]; }; then
          MISSING="$MISSING  $cite — no such path\n"
        fi
      elif [ -n "$line" ] && [ -f "$target" ]; then
        n=$(wc -l < "$target")
        [ "$line" -gt "$n" ] && MISSING="$MISSING  $cite — file has $n lines\n"
      fi
    done <<EOF
$CITES
EOF
    if [ -n "$MISSING" ]; then
      echo "stale-citation-gate: $REL cites paths that do not resolve — a rename, renumber or deletion elsewhere falsified them:" >&2
      printf '%b' "$MISSING" >&2
    fi
    exit 0 ;;
esac

case "$FILE" in
  *.py|*.ts|*.tsx|*.js|*.mjs|*.cjs|*.go|*.rs|*.rb|*.sh|*.sql|*.yml|*.yaml|*.scss|*.css|*.java|*.kt) ;;
  *) exit 0 ;;
esac

COMMENTS=$(grep -nE '^[[:space:]]*(#|//|/\*|\*|--|"""|'"'''"')' "$FILE" 2>/dev/null)
VOCAB=$(printf '%s\n' "$COMMENTS" | grep -Ei \
  -e '\bphases? [0-9]' \
  -e '\(D[0-9]{1,2}\)|\bper D[0-9]{1,2}\b|\bD[0-9]{1,2}:' \
  -e '\bAC[0-9]{1,2}\b' \
  -e 'written by the (coder|architect|assistant)|per the (architect|plan)' \
  -e 'an earlier version (said|had)')
HARD=$(grep -nE 'docs/plans/|ACCEPTANCE-CONTRACT|PLAN-IMPACT' "$FILE" 2>/dev/null)

HITS=$(printf '%s\n%s\n' "$VOCAB" "$HARD" | grep -v '^$' | sort -t: -k1,1n -u)
if [ -n "$HITS" ]; then
  echo "stale-citation-gate: planning vocabulary in shipped source $REL — keep the fact, cut the reference (see skills/_shared/code-vocabulary.md):" >&2
  printf '%s\n' "$HITS" | sed 's/^/  /' >&2
fi
exit 0
