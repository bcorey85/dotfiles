#!/usr/bin/env bash
# acceptance-stub-gate — refuse to dispatch a coder against a plan whose
# acceptance stubs were promised but never created.
#
# Why this exists: an acceptance stub is only an oracle because it was written
# before the implementation. A plan that defers stub creation to "before any
# coder is dispatched" has no mechanism behind that sentence — every phase can
# run to completion, the behaviors get covered by ordinary tests written after
# the code, and the one artifact that could not have been shaped by the
# implementation never exists. Nothing downstream notices, because the code
# works. This turns that sentence into a check.
#
# Run it from the main thread, with Bash, before the first coder dispatch of a
# plan. It is idempotent and cheap, so running it at every phase boundary is
# fine and is the safer default.
#
# Usage: acceptance-stub-gate.sh <plan-path>
#
# Exit codes:
#   0  PASS  — stub files exist and carry the ACCEPTANCE-CONTRACT marker
#   1  FAIL  — the plan promises stubs that are missing, empty, or unmarked
#   2  USAGE — bad invocation, unreadable plan, or missing dependency; DID NOT RUN
#   3  SKIP  — the plan has no Acceptance Stubs section (no behavioral criteria)
#
# Exit 2 is not a pass. If you see it, fix the invocation and run it again.
#
# The fix for exit 1 is never "write the stubs now, then dispatch" by an agent:
# acceptance-contract-gate makes these files immutable to agents, and an agent
# authoring its own oracle defeats the point. Stub authoring is the user's, in
# their editor, with the main thread.

set -uo pipefail

die_usage() {
  printf 'acceptance-stub-gate: USAGE ERROR — %s\n' "$1" >&2
  printf 'The check DID NOT RUN. This is not a pass.\n' >&2
  exit 2
}

[ $# -eq 1 ] || die_usage "expected exactly one argument (the plan path), got $#"
PLAN="$1"
[ -f "$PLAN" ] || die_usage "plan file not found: $PLAN"
command -v rg >/dev/null 2>&1 || die_usage "rg (ripgrep) is required and was not found"

# ---- locate the section -------------------------------------------------------
START=$(rg -n '^## Acceptance Stubs[[:space:]]*$' "$PLAN" | head -n 1 | cut -d: -f1)
if [ -z "$START" ]; then
  printf 'acceptance-stub-gate: SKIP — %s has no "## Acceptance Stubs" section.\n' "$PLAN"
  printf 'Treat as intentional only if the ticket genuinely has no behavioral criteria.\n'
  printf 'A behavioral ticket whose plan omits the section is a plan defect, not a pass.\n'
  exit 3
fi

# Section runs to the next H2 (or EOF).
NEXT=$(awk -v s="$START" 'NR>s && /^## / {print NR; exit}' "$PLAN")
[ -n "$NEXT" ] || NEXT=$(wc -l < "$PLAN")
SECTION=$(awk -v s="$START" -v e="$NEXT" 'NR>=s && NR<=e' "$PLAN")

# ---- parse the section --------------------------------------------------------
# Spec file(s) may be a path, a glob, or a directory. Take every backticked token
# on the Spec file(s) line; the template carries exactly one, but a plan naming a
# feature-root file and a feature-local dir is legitimate.
#
# Keep only tokens that could name a file. Real plans put prose on this line
# ("must carry `ACCEPTANCE-CONTRACT` in the first 10 lines"), and a backticked
# word with no path separator, glob, or extension is prose, not a target.
SPECS=$(printf '%s\n' "$SECTION" \
  | rg -N '^\s*-\s*\*\*Spec file\(s\)\*\*\s*:' \
  | rg -No '`[^`]+`' \
  | tr -d '`' \
  | rg -N '[/*.]' || true)

# Stub sentences: quoted bullets under the Stubs list. Comment lines in the
# template are HTML comments and carry no bullets, so they cannot inflate this.
STUB_COUNT=$(printf '%s\n' "$SECTION" | rg -Nc '^\s*-\s*"' || true)
STUB_COUNT=${STUB_COUNT:-0}

COUNT_CMD=$(printf '%s\n' "$SECTION" \
  | rg -N '^\s*-\s*\*\*Count command\*\*\s*:' \
  | rg -No '`[^`]+`' | head -n 1 | tr -d '`')

if [ -z "$SPECS" ]; then
  printf 'acceptance-stub-gate: FAIL — the Acceptance Stubs section names no Spec file(s).\n' >&2
  printf 'The section exists but points at nothing, so nothing can be verified.\n' >&2
  printf 'Fix the plan (add a backticked path or glob) before dispatching a coder.\n' >&2
  exit 1
fi

if [ "$STUB_COUNT" -eq 0 ]; then
  printf 'acceptance-stub-gate: FAIL — the Acceptance Stubs section lists no stub sentences.\n' >&2
  printf 'Spec file(s) named: %s\n' "$(printf '%s' "$SPECS" | tr '\n' ' ')" >&2
  exit 1
fi

# ---- resolve the spec files ---------------------------------------------------
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || ROOT=$(dirname "$PLAN")
cd "$ROOT" 2>/dev/null || die_usage "cannot enter repo root: $ROOT"

shopt -s nullglob globstar
FOUND=()
while IFS= read -r spec; do
  [ -n "$spec" ] || continue
  if [ -d "$spec" ]; then
    for f in "$spec"/**/*; do [ -f "$f" ] && FOUND+=("$f"); done
  else
    for f in $spec; do [ -f "$f" ] && FOUND+=("$f"); done
  fi
done <<< "$SPECS"

if [ ${#FOUND[@]} -eq 0 ]; then
  {
    printf 'acceptance-stub-gate: FAIL — %d stub sentence(s) promised, 0 spec files on disk.\n' "$STUB_COUNT"
    printf '\nPlan:        %s\n' "$PLAN"
    printf 'Spec file(s): %s\n' "$(printf '%s' "$SPECS" | tr '\n' ' ')"
    printf '\nThe plan promises acceptance stubs that were never created. Do NOT dispatch a\n'
    printf 'coder: once implementation exists, any test written against these behaviors is\n'
    printf 'no longer independent of it, and the contract cannot be recovered later.\n'
    printf '\nThese files are immutable to agents by design — ask the user to create them in\n'
    printf 'their editor from the section stub sentences, each carrying ACCEPTANCE-CONTRACT\n'
    printf 'in its first 10 lines. Report this and stop.\n'
  } >&2
  exit 1
fi

# ---- verify the marker --------------------------------------------------------
UNMARKED=()
for f in "${FOUND[@]}"; do
  head -n 10 "$f" 2>/dev/null | grep -q 'ACCEPTANCE-CONTRACT' || UNMARKED+=("$f")
done

if [ ${#UNMARKED[@]} -gt 0 ]; then
  {
    printf 'acceptance-stub-gate: FAIL — %d spec file(s) lack the ACCEPTANCE-CONTRACT marker.\n' "${#UNMARKED[@]}"
    printf '\nUnmarked:\n'
    printf '  %s\n' "${UNMARKED[@]}"
    printf '\nWithout the marker in the first 10 lines these files are ordinary tests: any\n'
    printf 'agent may weaken or delete them, so they are not an oracle. Ask the user to add\n'
    printf 'the marker. Report this and stop.\n'
  } >&2
  exit 1
fi

printf 'acceptance-stub-gate: PASS — %d stub sentence(s) promised; %d marked spec file(s) present.\n' \
  "$STUB_COUNT" "${#FOUND[@]}"
printf '  %s\n' "${FOUND[@]}"
if [ -n "$COUNT_CMD" ]; then
  printf '\nRemaining-stub count command from the plan (run it yourself to see how many are\n'
  printf 'still unflipped; a phase that flips none is not progressing the contract):\n  %s\n' "$COUNT_CMD"
fi
printf '\nChecked: the promised files exist and are agent-immutable. NOT checked: whether\n'
printf 'each stub sentence has a corresponding assertion, or whether the assertions are\n'
printf 'at the criterion boundary. Those need a reader.\n'
exit 0
