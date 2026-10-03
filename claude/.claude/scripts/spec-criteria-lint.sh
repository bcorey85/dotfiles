#!/usr/bin/env bash
# spec-criteria-lint — static lint of an implementation plan's verification
# criteria, run at eng-spec finalization BEFORE any coder is dispatched.
#
# Why this exists: a plan's `#### Automated Verification:` commands are authored
# at plan time and not executed until branch end (plan-verifier). One failure
# shape is invisible to a human READING the plan and costs a whole branch built
# against a broken oracle: a verification command names a concrete file that
# does not exist and that no phase creates — a criterion pointing at an artifact
# a later decision retired. Report-only: a path created at runtime is a
# legitimate miss.
#
# This script is STATIC ONLY. It never executes a verification command — those
# can be migrations or destructive ops. The falsifiability dry-run (run the
# read-only commands, classify red / already-green / argv-broken) is a judgment
# step in eng-spec phase 6, gated to non-destructive commands.
#
# usage: spec-criteria-lint.sh <plan.md>
# exit:  0 clean · 1 findings printed · 2 usage/parse error
set -euo pipefail

plan="${1:-}"
[ -z "$plan" ] && { echo "usage: spec-criteria-lint.sh <plan.md>" >&2; exit 2; }
[ -f "$plan" ] || { echo "no such plan file: $plan" >&2; exit 2; }

findings=0

# ---- Concrete verification-command paths that exist nowhere ----
# Collect every **File** target (paths a phase creates), then scan Automated
# Verification command backticks for concrete file paths (contain '/', end in a
# known extension, no glob/wildcard). Flag those absent from disk and from the
# File-target set. Report-only.
repo_root=$(git -C "$(dirname "$plan")" rev-parse --show-toplevel 2>/dev/null || pwd)

created_paths=$(grep -E '^\*\*File\*\*:' "$plan" \
  | sed -E 's/^\*\*File\*\*:[[:space:]]*//; s/`//g' | awk '{print $1}' | sort -u || true)

is_created() {
  printf '%s\n' "$created_paths" | grep -Fxq "$1"
}

# Pull backticked spans only from within Automated Verification sections.
in_av=0
declare -A seen_orphan=()
while IFS= read -r line; do
  case "$line" in
    '#### Automated Verification:'*) in_av=1; continue ;;
    '####'*|'###'*|'## '*) in_av=0 ;;
  esac
  [ "$in_av" -eq 1 ] || continue
  # tokens that look like a concrete file: have a slash and a dotted extension,
  # no shell glob metachar.
  for tok in $(printf '%s' "$line" | grep -oE '[[:alnum:]_./-]+\.[[:alnum:]]{1,5}' || true); do
    case "$tok" in
      *'*'*|*'...'*|http*|./|../) continue ;;
      */*) ;;
      *) continue ;;
    esac
    [ -n "${seen_orphan[$tok]:-}" ] && continue
    seen_orphan[$tok]=1
    [ -e "$repo_root/$tok" ] && continue
    [ -e "$tok" ] && continue
    is_created "$tok" && continue
    if [ "$findings" -eq 0 ]; then echo "## spec-criteria-lint findings — $plan"; echo; fi
    findings=$((findings + 1))
    echo "- **orphan-verification-path**: \`$tok\` is named in a verification command,"
    echo "  but it exists nowhere on disk and no phase's **File** creates it."
    echo "  Confirm a later decision did not retire it (or it is a runtime path — then ignore)."
  done
done < "$plan"

if [ "$findings" -eq 0 ]; then
  echo "spec-criteria-lint: clean — $plan"
  exit 0
fi
echo
echo "$findings finding(s). Resolve with the user before Phase 7, like a DESIGN GAP."
exit 1
