#!/usr/bin/env bash
# qrspi-resolve-dir.sh — resolve the QRSPI task directory under docs/eng-specs/
# Shared by /q-research, /q-design, /q-structure, /q-plan, /q-finalize.
#
# usage: qrspi-resolve-dir.sh [<path-or-ticket>]
#   <path>    existing directory -> used directly
#   <ticket>  e.g. IQ-400 (case-insensitive) -> glob docs/eng-specs/IQ-400-*/
#   (empty)   infer ticket from the current branch name (TICKET-NUM-prefix)
#
# exit 0: exactly one match, printed on stdout
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
  0) echo "no task directory matching $specs/$ticket-*/" >&2; exit 4 ;;
  1) printf '%s' "$found"; exit 0 ;;
  *) printf '%s' "$found"; exit 3 ;;
esac
