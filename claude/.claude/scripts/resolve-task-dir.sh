#!/usr/bin/env bash
# resolve-task-dir.sh — resolve the /eng-spec task directory under docs/eng-specs/
# Shared by /verify, /branch-recap, /code, and /adr. Do NOT reimplement inline.
#
# usage: resolve-task-dir.sh [<path-or-ticket>]
#   <path>    existing directory -> used directly
#   <ticket>  e.g. IQ-400 (case-insensitive) -> glob docs/eng-specs/IQ-400-*/
#             (task dir), else docs/eng-specs/IQ-400*.md (legacy flat plan)
#   (empty)   infer ticket from the current branch name (TICKET-NUM-prefix)
#
# exit 0: exactly one task DIRECTORY match, printed on stdout. The plan inside
#         it is spec.md; the ticket is 00-ticket.md.
# exit 5: no task dir, exactly one legacy flat eng-spec plan FILE, printed
# exit 3: multiple matches, all printed on stdout (caller asks the user)
# exit 4: nothing resolvable (caller asks the user for a path)
set -euo pipefail

arg="${1:-}"
specs="docs/eng-specs"

if [ -n "$arg" ] && [ -d "$arg" ]; then
  printf '%s\n' "${arg%/}"
  exit 0
fi

ticket=""
if printf '%s' "$arg" | grep -qE '^[A-Za-z]+-[0-9]+$'; then
  ticket=$(printf '%s' "$arg" | tr '[:lower:]' '[:upper:]')
else
  ticket=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | grep -oE '^[a-zA-Z]+-[0-9]+' | tr '[:lower:]' '[:upper:]' || true)
fi

if [ -z "$ticket" ]; then
  echo "no ticket in arguments or branch name" >&2
  exit 4
fi

count=0
found=""
for d in "$specs/$ticket"-*/; do
  [ -d "$d" ] || continue
  count=$((count + 1))
  found="${found}${d%/}
"
done

case "$count" in
  0) : ;; # no task dir — fall through to the eng-spec file lookup
  1) printf '%s' "$found"; exit 0 ;;
  *) printf '%s' "$found"; exit 3 ;;
esac

fcount=0
ffound=""
for f in "$specs/$ticket"*.md; do
  [ -f "$f" ] || continue
  fcount=$((fcount + 1))
  ffound="${ffound}${f}
"
done

case "$fcount" in
  0) echo "no task directory or eng-spec matching $specs/$ticket*" >&2; exit 4 ;;
  1) printf '%s' "$ffound"; exit 5 ;;
  *) printf '%s' "$ffound"; exit 3 ;;
esac
