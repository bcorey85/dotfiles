#!/usr/bin/env bash
# dead-symbol-scan — find symbols that no production code references.
#
# Why this exists: a phase can kill code it never opens. Phase 3 ships a new
# selection path and Phase 1's field stops having a writer; a later phase builds
# its own envelope and an earlier wrapper is orphaned. Each phase's diff is
# individually clean, so a diff-bound reviewer cannot see it — only a whole-tree
# view can, and by the time anyone takes one the branch is done.
#
# Two classes, and the second is the one general tooling misses:
#
#   UNREFERENCED — no reference anywhere outside the declaring file.
#   TEST-ONLY    — referenced ONLY from test files. Production-dead: the tests
#                  keep it compiling and keep it off every unused-symbol report,
#                  because in Go and in most TS setups a test IS a consumer.
#                  staticcheck's U1000 and knip both count that as "used".
#
# Report-only by design. Every finding is a CANDIDATE, not a verdict — see the
# false-positive list printed with the results. Never delete on its say-so alone.
#
# Languages: Go, and TS/JS (ESM `export` syntax; --ts covers both).
#
# NOT supported, deliberately: Python and C#. Python has no export marker, so
# "public" would have to mean "module-level and not underscore-prefixed", and
# both languages lean on reflection, DI containers, and attribute/decorator
# dispatch that textual counting cannot see. A scan there would be mostly false
# positives, which is worse than no scan — it teaches the reader to skim. If you
# need those languages, use a real call-graph tool, not this.
#
# Usage: dead-symbol-scan.sh <dir> [--go|--ts]     (language auto-detected)
#
# Exit codes:
#   0  ran successfully (findings or not — read the report)
#   2  USAGE — bad invocation or missing dependency; DID NOT RUN

set -uo pipefail

die_usage() {
  printf 'dead-symbol-scan: USAGE ERROR — %s\n' "$1" >&2
  printf 'The scan DID NOT RUN. Absence of findings here means nothing.\n' >&2
  exit 2
}

[ $# -ge 1 ] || die_usage "expected a directory to scan"
DIR="$1"; shift
[ -d "$DIR" ] || die_usage "not a directory: $DIR"
command -v rg >/dev/null 2>&1 || die_usage "rg (ripgrep) is required and was not found"

LANG_MODE=auto
while [ $# -gt 0 ]; do
  case "$1" in
    --go) LANG_MODE=go ;;
    --ts) LANG_MODE=ts ;;
    *) die_usage "unknown option: $1" ;;
  esac
  shift
done

cd "$DIR" || die_usage "cannot enter $DIR"

if [ "$LANG_MODE" = auto ]; then
  if [ -n "$(rg -l --type go '' 2>/dev/null | head -1)" ]; then LANG_MODE=go
  elif [ -n "$(rg -l --type ts --type js '' 2>/dev/null | head -1)" ]; then LANG_MODE=ts
  else die_usage "no Go or TS/JS sources found under $DIR (pass --go or --ts to force).
Python and C# are NOT supported by this scan — see the header. Do not read this as clean."; fi
fi

# ---- file sets ----------------------------------------------------------------
case "$LANG_MODE" in
  go)
    PROD=$(rg -l --type go '' | rg -v '_test\.go$' || true)
    TESTS=$(rg -l --type go '' | rg '_test\.go$' || true)
    ;;
  ts)
    # rg's `ts` type already includes .tsx; there is no `tsx` type, and passing one
    # makes rg exit non-zero, which silently emptied the file list on every TS repo.
    # `js` is scanned in the same mode: ESM export syntax is identical.
    PROD=$(rg -l --type ts --type js '' 2>/dev/null | rg -v '\.(test|spec)\.[cm]?[jt]sx?$' || true)
    TESTS=$(rg -l --type ts --type js '' 2>/dev/null | rg '\.(test|spec)\.[cm]?[jt]sx?$' || true)
    ;;
esac
[ -n "$PROD" ] || die_usage "no production sources found under $DIR"

PRODLIST=$(mktemp); TESTLIST=$(mktemp)
trap 'rm -f "$PRODLIST" "$TESTLIST"' EXIT
printf '%s\n' "$PROD" > "$PRODLIST"
printf '%s\n' "$TESTS" > "$TESTLIST"

# ---- collect declarations ----------------------------------------------------
# file<TAB>symbol. Methods are deliberately excluded in Go: a method with no
# direct caller may exist solely to satisfy an interface, which is a real use
# this scan cannot see. Reporting them would bury the true positives.
DECLS=$(mktemp); trap 'rm -f "$PRODLIST" "$TESTLIST" "$DECLS"' EXIT

case "$LANG_MODE" in
  go)
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      rg -No '^func ([A-Z][A-Za-z0-9_]*)\(' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
      rg -No '^type ([A-Z][A-Za-z0-9_]*)\b' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
      rg -No '^(?:var|const) ([A-Z][A-Za-z0-9_]*)\b' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
    done < "$PRODLIST" > "$DECLS"
    ;;
  ts)
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      rg -No '^export (?:async )?function ([A-Za-z_][A-Za-z0-9_]*)' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
      rg -No '^export (?:const|let) ([A-Za-z_][A-Za-z0-9_]*)' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
      rg -No '^export (?:class|interface|type|enum) ([A-Za-z_][A-Za-z0-9_]*)' -r '$1' "$f" 2>/dev/null \
        | while IFS= read -r s; do printf '%s\t%s\n' "$f" "$s"; done
    done < "$PRODLIST" > "$DECLS"
    ;;
esac

TOTAL=$(wc -l < "$DECLS" | tr -d ' ')
[ "$TOTAL" -gt 0 ] || die_usage "found no exported declarations to check — the declaration patterns may not fit this codebase"

# ---- Go entry points and framework hooks that are called by machinery --------
is_exempt() {
  case "$1" in
    main|init|String|Error|Unwrap|MarshalJSON|UnmarshalJSON|ServeHTTP) return 0 ;;
  esac
  return 1
}

# ---- classify ----------------------------------------------------------------
# A use inside the declaring file counts as a use. An exported type consumed by
# its own file's functions is alive, and excluding the declaring file marks every
# such type dead — the first version of this script did exactly that and produced
# nothing but false positives.
#
# So: count every reference that is neither the declaration itself nor a comment.
# This is deliberately conservative. It cannot tell a live use from a use by
# other dead code (that needs a call graph), so it reports only symbols with no
# surviving reference at all. Fewer findings, each one strong.
PRODFILES=$(tr '\n' ' ' < "$PRODLIST")
TESTFILES=$(tr '\n' ' ' < "$TESTLIST")

real_refs() {  # symbol, file-list -> count of non-declaration, non-comment refs
  local sym="$1" files="$2"
  [ -n "$files" ] || { printf '0'; return; }
  # Filter ONLY this symbol's own declaration line, never every line that starts
  # with a keyword: `func main() { ... LiveHelper() ... }` begins with `func` and
  # is a use, not a declaration. Filtering by keyword alone erases exactly the
  # uses that prove a symbol alive.
  rg -w --no-filename "$sym" $files 2>/dev/null \
    | rg -v '^\s*(//|\*|/\*)' \
    | rg -v "^(func|type|var|const)\s+${sym}\b" \
    | rg -v "^export\s+(async\s+)?(function|const|let|class|interface|type|enum)\s+${sym}\b" \
    | rg -c . 2>/dev/null || printf '0'
}

UNREF=(); TESTONLY=()
while IFS=$'\t' read -r file sym; do
  [ -n "$sym" ] || continue
  is_exempt "$sym" && continue

  prod_hits=$(real_refs "$sym" "$PRODFILES")
  [ "${prod_hits:-0}" -gt 0 ] && continue

  test_hits=$(real_refs "$sym" "$TESTFILES")

  if [ "${test_hits:-0}" -gt 0 ]; then
    # A helper package that exists to serve tests is test-only by construction,
    # not by decay. Reporting it every run trains the reader to skim the section.
    case "$file" in
      *testsupport*|*testutil*|*testhelper*|*testdata*|*/fixtures/*|*mocks*) continue ;;
    esac
    TESTONLY+=("$file:$sym ($test_hits test reference(s))")
  else
    UNREF+=("$file:$sym")
  fi
done < "$DECLS"

# ---- report ------------------------------------------------------------------
printf 'dead-symbol-scan: %s — %d exported declaration(s) checked in %s\n' \
  "$LANG_MODE" "$TOTAL" "$DIR"
printf '\n'

if [ ${#TESTONLY[@]} -gt 0 ]; then
  printf 'TEST-ONLY (%d) — production-dead; only tests reference these. A test is a\n' "${#TESTONLY[@]}"
  printf 'consumer to every compiler and to staticcheck/knip, so nothing else reports them.\n'
  printf 'Ask of each: is this a symbol kept alive by the test written to cover it?\n\n'
  printf '  %s\n' "${TESTONLY[@]}"
  printf '\n'
fi

if [ ${#UNREF[@]} -gt 0 ]; then
  printf 'UNREFERENCED (%d) — no reference anywhere in production or test code,\n' "${#UNREF[@]}"
  printf 'including the declaring file itself.\n'
  printf 'On a multi-phase branch, check whether a LATER phase orphaned it: the symbol is\n'
  printf 'in a file that phase never opened, which is why no diff review could see it.\n\n'
  printf '  %s\n' "${UNREF[@]}"
  printf '\n'
fi

if [ ${#TESTONLY[@]} -eq 0 ] && [ ${#UNREF[@]} -eq 0 ]; then
  printf 'No candidates.\n\n'
fi

cat <<'CAVEATS'
These are CANDIDATES. This is textual reference counting, not type resolution.
Known false-positive sources — check each finding before acting:
  - a symbol reached only through an interface, embedding, or a function value
  - reflection, struct tags, code generation, or any string-keyed dispatch
  - a public API deliberately exported for consumers outside this tree
  - TS: barrel/index re-exports, framework-convention entry points, JSX used
    only in a file this scan classed as a test
  - Go methods are NOT scanned at all (interface satisfaction is invisible here)
  - MID-BRANCH: "not yet wired" looks identical to "orphaned". A symbol whose
    only caller is a phase that has not run yet reports as dead. This is why the
    scan is read at a phase boundary and acted on at the last one.
False negatives are likelier than false positives: a same-named symbol anywhere
in production counts as a reference, so shadowed and common names slip through.
CAVEATS
exit 0
