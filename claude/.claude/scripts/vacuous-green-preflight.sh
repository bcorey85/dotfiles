#!/usr/bin/env bash
# vacuous-green-preflight.sh — mechanical detector for three shapes of test that
# PASSES WITHOUT EXERCISING ANYTHING.
#
# A green result is evidence only if something ran. These three shapes all report
# green while checking nothing, and all three are decidable by reading text — no
# execution, no intent judgment, no model verdict:
#
#   A. zero-match filter  — `go test -run X` (or -k / -t) whose pattern matches no
#                           test in the tree. The gate passes because it ran zero
#                           tests. Observed 3× in one phase.
#   B. absentee subject   — a test named for a symbol its own file never calls.
#                           `TestBuildIncremental_X` that reimplements the loop
#                           locally and asserts on its own variables.
#   C. string-matched     — a guard asserting on a literal fragment of the source
#      guard               it guards. Renaming a local variable bypasses it, and
#                           the suite stays green.
#
# Why a script and not a reviewer instruction: shape B survived the test-intent
# gate, the drift gate, AND a human analyst's read in the same phase. A class that
# gets past three oracles needs a mechanical check, not more attention.
#
# This is a DETECTOR OF THREE KNOWN SHAPES, not a proof of non-vacuity. It always
# prints what it actually checked — a clean result on a language it does not
# support is a no-op, and saying so is the entire point of the tool.
#
# Measured before shipping, on two real Go suites (31 + 17 test files):
#   2 findings, both true positives, 0 false positives.
# Getting there required three corrections that the "just grep for it" framing
# hides, each recorded at its check below:
#   - B must be scoped to the test's OWN BODY, not its file. The instance this
#     was built for sits in a file whose other tests call the symbol 20 times.
#   - B must require the name to be a REAL declared symbol. Without that it fired
#     on 41 of 31 files (TestWire_*, TestAuth_*, TestAC10_* — topic prefixes).
#   - C must require the test to read source code as data. Without that it fired
#     on every shared import path and fixture string: ~50 findings, all noise.
# The first two drafts of this script would each have passed a green run while
# detecting nothing — which is the shape it exists to catch. Re-measure after
# any edit; a pre-flight nobody trusts is worse than no pre-flight.
#
# Language coverage:
#   A  — any language (it reads the command, not the code)
#   B  — Go, Python, and TS/JS. Go and Python take the subject from the test
#        FUNCTION name; TS/JS takes it from the `describe()` block name, because
#        `it('returns 404 when the token is expired')` is prose and names nothing.
#   C  — any language whose tests read source files as data
#
# Measured for the TS/JS addition, on two real suites (510 test files, 325
# checkable describe blocks): 0 findings, 0 false positives, against 11 planted
# fixture cases of which the 4 true vacuous ones all fire. It took four more
# corrections, each recorded at its site:
#   - the symbol universe must come from RESOLVED IMPORTS, not the test's own
#     directory. TS tests live in `test/unit/`; Go's `foo_test.go` sits beside
#     `foo.go`. Directory-only left 3 of 4 suites with ZERO eligible blocks.
#   - the subject must be an EXPORTED symbol. A test cannot call what the module
#     keeps private, so "never calls it" is not a defect there.
#   - depth-1 helper inlining, same-file AND for imported TEST helpers, because
#     TS suites construct the subject in a `freshStore()` factory. Restricted to
#     test-support paths: inline arbitrary source and a block that exercises a
#     NEIGHBOURING function clears on its own module's text.
#   - every path is matched only after norm_path(). `test/unit/../../src/x.ts`
#     contains the literal `test/`, which made the subject's own module pass a
#     test-helper filter and silently cleared a planted defect.
#
# Two portability rules this file learned the hard way, both of which produced a
# SILENT no-op rather than an error — see the comments at references_in_body and
# check_b_ts:
#   - no `grep -q` as the last stage of a pipeline (SIGPIPE + pipefail turns a
#     match into a miss, and only on bodies large enough to still be writing)
#   - nothing bash-4-only (macOS ships 3.2; a missing `mapfile` under `set -u`
#     leaves the walk empty and prints a clean result for the whole platform)
#
# Usage:
#   vacuous-green-preflight.sh files <test-file>...     # checks B and C
#   vacuous-green-preflight.sh cmd '<test command>'     # check A
#   vacuous-green-preflight.sh both '<cmd>' <file>...   # both
#
# Exit: 0 = nothing suspect (read the coverage line!), 1 = suspect findings,
#       2 = usage error. Suspect ≠ defect: each finding names what to confirm.
set -uo pipefail

command -v rg >/dev/null || { echo "vacuous-green-preflight: rg not found"; exit 2; }

FINDINGS=0
C_SKIPPED=0
TS_BLOCKS=0
TS_ELIGIBLE=0
CHECKED=()

note() { printf '  %s\n' "$*"; }
finding() {
  FINDINGS=$((FINDINGS + 1))
  printf '\nSUSPECT [%s] %s\n' "$1" "$2"
  shift 2
  for l in "$@"; do printf '    %s\n' "$l"; done
}

# ---------------------------------------------------------------- check A
# A test-filter flag whose pattern matches no test name that exists.
check_cmd() {
  local cmd="$1" pat="" kind=""

  if [[ "$cmd" =~ -run[[:space:]]+\'?\"?([^[:space:]\'\"]+) ]]; then
    pat="${BASH_REMATCH[1]}"; kind="go"
  elif [[ "$cmd" =~ (--testNamePattern|-t)[[:space:]]+\'?\"?([^\'\"]+)\'?\"? ]]; then
    pat="${BASH_REMATCH[2]}"; kind="js"
  elif [[ "$cmd" =~ -k[[:space:]]+\'?\"?([^\'\"]+)\'?\"? ]]; then
    pat="${BASH_REMATCH[1]}"; kind="py"
  else
    CHECKED+=("A: no test-name filter in the command — nothing to check")
    return
  fi

  # Collect the test names that actually exist.
  local names
  case "$kind" in
    go) names=$(rg --no-filename -o -r '$1' '^func (Test[A-Za-z0-9_]+)' -g '*_test.go' . 2>/dev/null) ;;
    py) names=$(rg --no-filename -o -r '$1' '^\s*(?:async )?def (test_[A-Za-z0-9_]+)' -g '*test*.py' . 2>/dev/null) ;;
    js) names=$(rg --no-filename -o -r '$1' '(?:^|\s)(?:it|test)\(\s*[`'"'"'"]([^`'"'"'"]+)' -g '*.{test,spec}.{js,ts,jsx,tsx}' . 2>/dev/null) ;;
  esac

  if [[ -z "$names" ]]; then
    CHECKED+=("A: found no $kind test names in the tree — check skipped, NOT passed")
    finding "A" "cannot enumerate $kind tests, so the filter '$pat' is unverifiable" \
      "The command filters tests but this script found no test declarations to match against." \
      "Confirm by hand that '$pat' selects at least one test before trusting a green run."
    return
  fi

  # Go's -run and JS's -t are unanchored regexes; a Go pattern may be slash-separated
  # (parent/subtest) — only the first segment selects top-level functions.
  local probe="$pat"
  [[ "$kind" == "go" ]] && probe="${pat%%/*}"

  local hits
  if [[ "$kind" == "py" ]]; then
    # pytest -k is a boolean expression over substrings, not a regex. Approximate:
    # at least one bare identifier in the expression must be a substring of a name.
    hits=""
    for tok in $(printf '%s' "$probe" | tr -c 'A-Za-z0-9_' ' '); do
      case "$tok" in and|or|not|"") continue ;; esac
      if printf '%s\n' "$names" | grep -F -- "$tok" >/dev/null; then hits="x"; break; fi
    done
  else
    hits=$(printf '%s\n' "$names" | grep -E -- "$probe" || true)
  fi

  local total; total=$(printf '%s\n' "$names" | grep -c . || true)
  if [[ -z "$hits" ]]; then
    finding "A" "test filter selects ZERO tests — this gate passes vacuously" \
      "pattern: $probe   (from: $cmd)" \
      "$total $kind test(s) exist; none match. A green run here means nothing executed." \
      "Fix the pattern or drop the filter. Do NOT record this command as evidence."
  else
    CHECKED+=("A: filter '$probe' matches at least one of $total $kind tests")
  fi
}

# ------------------------------------------------------------- checks B, C
check_files() {
  local any_go=0 any_py=0 any_ts=0 skipped=()

  for f in "$@"; do
    [[ -f "$f" ]] || { skipped+=("$f (not a file)"); continue; }
    case "$f" in
      *_test.go)                                any_go=1; check_b "$f" go ;;
      *test*.py|*_test.py)                      any_py=1; check_b "$f" py ;;
      *.test.ts|*.test.tsx|*.test.js|*.test.jsx|*.test.mts|*.test.cts|\
      *.spec.ts|*.spec.tsx|*.spec.js|*.spec.jsx|*.spec.mts|*.spec.cts)
                                                any_ts=1; check_b_ts "$f" ;;
      *.test.*|*.spec.*)                        skipped+=("$f (JS/TS shape B covers .ts/.tsx/.js/.jsx/.mts/.cts only)") ;;
      *)                                        skipped+=("$f (unrecognized test file type)") ;;
    esac
    check_c "$f"
  done

  (( any_go )) && CHECKED+=("B: Go test files checked for absentee subject")
  (( any_py )) && CHECKED+=("B: Python test files checked for absentee subject")
  # The eligibility ratio is the honest coverage number for TS and it is usually
  # small: a describe name has to be identifier-shaped AND a declared symbol
  # before this check can say anything at all. Printing "0 findings" without it
  # would be the same false pass the whole script exists to refuse.
  (( any_ts )) && CHECKED+=("B: TS/JS — $TS_ELIGIBLE of $TS_BLOCKS describe() block(s) had a name that is both identifier-shaped and a declared symbol; only those could be checked. it() names are prose and are never checked.")
  CHECKED+=("C: string-matched guard checked on $(($# - C_SKIPPED)) of $# file(s) — $C_SKIPPED never read source as data, so there was nothing for C to check")

  if (( ${#skipped[@]} )); then
    CHECKED+=("B: NOT checked for ${#skipped[@]} file(s) — a clean result does not cover them:")
    for s in "${skipped[@]}"; do CHECKED+=("     - $s"); done
  fi
}

# Does the test's OWN BODY (not its file) mention $1 on a non-comment line?
#
# File scope is the tempting implementation and it is wrong. The instance this
# check exists for — a `TestBuildIncremental_*` that calls `Build` instead — sits
# in a file whose OTHER tests reference `BuildIncremental` twenty times over. A
# file-scoped check reports that file clean, which is a vacuous vacuity check.
#
# Comments are excluded because a comment naming the function is the single most
# likely thing to appear in a test that does not call it: whoever wrote the
# vacuous test still described the intent accurately.
# NEVER use `grep -q` as the last stage of these pipelines. This file runs under
# `set -o pipefail`, and -q exits on the FIRST match, closing the pipe while the
# upstream grep is still writing; upstream dies with SIGPIPE (141) and pipefail
# hands that back as the pipeline's status, so a match is reported as a miss.
# It is size-dependent — small bodies finish before the pipe closes — so it
# reads as "works" on a fixture and silently manufactures findings on a real
# suite. Measured: it turned a 2,500-line describe block that calls its subject
# 33 times into a shape-B finding. Redirect to /dev/null instead; grep without
# -q drains its input.
references_in_body() {
  printf '%s\n' "$2" | grep -Ev '^[[:space:]]*(//|#|\*|/\*)' | grep -F -- "$1" >/dev/null
}

# As above, but matches the subject as a case-insensitive SUBSTRING.
#
# Only check_b_ts uses this, and it is the TS equivalent of the prefix-stripping
# concession Go and Python get. Measured cause: `describe('fetchWithRefresh')`
# over a factory whose export is `createFetchWithRefresh` — the test calls the
# factory and invokes the returned closure under a local name, so the symbol
# never appears verbatim while the behavior is fully exercised. Factory,
# `create*`/`make*`/`use*` wrappers, and method-on-instance access all produce
# this shape, and it is the dominant naming convention in a TS codebase.
#
# It under-reports by exactly the amount that concession costs. The shape B must
# catch — a body that never mentions the subject in ANY form because it
# reimplements the logic locally — survives it untouched.
references_in_body_ci() {
  printf '%s\n' "$2" | grep -Ev '^[[:space:]]*(//|#|\*|/\*)' | grep -Fi -- "$1" >/dev/null
}

# A test name is `<subject><case description>` with no marker for where the subject
# ends, so try every prefix: the whole name, then one trailing word at a time. Any
# prefix referenced in the body clears the test. This deliberately under-reports —
# `TestAuthorizeRejectsExpired` clears on `Authorize` even if the `RejectsExpired`
# half is untested — because a pre-flight that cries wolf gets switched off, and
# the shape it must catch (NO prefix appears at all) survives the concession.
subject_referenced() {
  local sym="$1" body="$2" strip="$3" cand="$sym" next
  while [[ ${#cand} -ge 4 ]]; do
    references_in_body "$cand" "$body" && return 0
    next="${cand%$strip}"
    [[ "$next" == "$cand" ]] && break   # no separator left to strip
    cand="$next"
  done
  return 1
}

# Every symbol declared in the non-test sources beside $1, one per line.
#
# This set is what makes check B usable. Test names are `Test<Topic>_<Case>` at
# least as often as `Test<Symbol>_<Case>`, and a topic prefix — `TestWire_*`,
# `TestAuth_*`, `TestAC10_*` — names nothing that could ever be called. Measured
# on a 31-file Go suite, requiring the prefix to be a REAL declared symbol cut
# check B from 41 findings to a handful. Without it the check is unshippable:
# a gate that fires on a third of a healthy suite gets muted, not read.
declared_symbols() {
  local dir; dir=$(dirname "$1")
  case "$2" in
    go) rg --no-filename -o -r '$1' '^func (?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)' \
          --glob '!*_test.go' -g '*.go' "$dir" 2>/dev/null ;;
    py) rg --no-filename -o -r '$1' '^(?:class |(?:async )?def )([A-Za-z_][A-Za-z0-9_]*)' \
          --glob '!*test*.py' -g '*.py' "$dir" 2>/dev/null ;;
    # EXPORTED declarations only, plus `export { ... }` lists. A test cannot call
    # what its subject's module keeps private, so "named for it but never calls
    # it" cannot be a defect there. Measured: `describe('FocusedAppContext')` over
    # a module whose `const FocusedAppContext = createContext(...)` is private —
    # the test drives the public `FocusedAppProvider`/`useFocusedApp` pair, which
    # is the only way it COULD be driven. Requiring export also removes the whole
    # class of describe blocks named after the module rather than a symbol,
    # because a module name only collides with a private internal.
    ts) { ts_source_files "$1" | tr '\n' '\0' | xargs -0 -r rg --no-filename -o -r '$1' \
            '^export\s+(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?(?:function|class|const|let|var|type|interface|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)' \
            2>/dev/null
          ts_source_files "$1" | tr '\n' '\0' | xargs -0 -r rg --no-filename -o -r '$1' \
            '^export\s*\{([^}]*)\}' 2>/dev/null \
            | tr ',' '\n' | sed -E 's/.* as //; s/[^A-Za-z0-9_$]//g' | grep -v '^$'
        } ;;
  esac
}

# The source files a TS test is actually about: its own directory PLUS whatever
# its relative imports resolve to.
#
# The directory alone is what Go and Python use, and it is correct there because
# `foo_test.go` sits beside `foo.go`. TS does not work that way. Measured on four
# real suites: with a directory-only symbol set, THREE of the four had ZERO
# eligible describe blocks — their tests live in `test/unit/api/` while the
# source lives in `src/api/`, so the directory scan reads a folder containing
# nothing but other tests. The check ran, found nothing, and reported clean.
#
# That is this script's own failure mode, reached from the inside. Imports are
# the fix because a TS test names its subject in exactly one reliable place: the
# import it had to write to call it.
ts_source_files() {
  local f="$1" dir spec
  dir=$(dirname "$f")

  find "$dir" -maxdepth 1 -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' \
       -o -name '*.jsx' -o -name '*.mts' -o -name '*.cts' \) \
       ! -name '*.test.*' ! -name '*.spec.*' ! -name '*.d.ts' 2>/dev/null

  while IFS= read -r spec; do
    ts_resolve "$dir" "$spec"
  done < <(rg --no-filename -o -r '$1' '(?:from|require\()\s*['"'"'"]([./][^'"'"'"]*)' "$f" 2>/dev/null | sort -u)
}

# Collapse `a/b/../c` to `a/c`. Textual on purpose: `realpath` is not on a stock
# macOS. Required before any path is pattern-matched — a test at `test/unit/`
# importing `../../src/store.ts` yields a path whose raw text contains `test/`,
# which made the subject's own module match a test-helper filter and cleared the
# very shape B is looking for.
norm_path() {
  local part joined n
  local -a out=()
  local IFS=/
  for part in $1; do
    case "$part" in
      .|"") ;;
      ..) n=${#out[@]}
          if (( n )) && [[ "${out[$((n - 1))]}" != ".." ]]; then
            out=("${out[@]:0:$((n - 1))}")
          else
            out=("${out[@]}" "..")
          fi ;;
      *)  out=("${out[@]}" "$part") ;;
    esac
  done
  joined="${out[*]}"
  [[ "$1" == /* ]] && joined="/$joined"
  printf '%s\n' "$joined"
}

# One relative import specifier -> the file(s) on disk it can mean.
ts_resolve() {
  local base="$1/${2%.js}" cand    # TS source is imported with a .js suffix under NodeNext
  base="${base%.ts}"
  for cand in "$base".ts "$base".tsx "$base".mts "$base".cts "$base".js "$base".jsx \
              "$base"/index.ts "$base"/index.tsx "$base"/index.js; do
    [[ -f "$cand" ]] && printf '%s\n' "$cand"
  done
}

# TS/JS shape B. The subject cannot come from the test name the way it does in
# Go and Python: `it('returns 404 when the token is expired')` is prose, not an
# identifier, so there is nothing to match against declared symbols.
#
# The `describe()` block name is the one place a JS-family suite conventionally
# writes the subject as an identifier — `describe('parseToken', ...)`. That is
# the whole basis of this check, and it is why the check is per-describe-block
# rather than per-test: a single `it()` is not named for anything.
#
# All three of the corrections the Go/Python version needed apply unchanged, and
# the third one does most of the work here. Measured on 527 test files across
# four real suites, `describe()` names are prose far more often than identifiers
# ('role enforcement', 'error and edge paths (coverage round)', 'User Model'),
# so BOTH filters are load-bearing: identifier-SHAPED, and a REAL declared
# symbol. Shape alone would fire on every one-word prose describe.
#
# No prefix-stripping, unlike Go/Python: the subject here is required to match a
# declared symbol exactly, so there is no `<subject><case>` concatenation left to
# peel apart.
check_b_ts() {
  local f="$1" starts i start end line raw sym body indent nindent syms eof
  syms=$(declared_symbols "$f" ts)
  [[ -n "$syms" ]] || return 0

  # One rg pass for both the line numbers and the lines themselves — re-reading
  # each line with sed is O(blocks²) per file, and a real suite has >1000 blocks.
  # `while read` rather than `mapfile`: macOS ships bash 3.2, where mapfile does
  # not exist. Under `set -u` that failure is silent — the array stays empty, the
  # walk covers nothing, and the script prints "0 findings" on an entire platform.
  # Nothing bash-4-only may enter this file for that reason (no mapfile, no
  # `declare -A`, no negative array indices).
  local rl
  starts=(); local -a texts=() indents=()
  while IFS= read -r rl; do
    starts+=("${rl%%:*}")
    texts+=("${rl#*:}")
  done < <(rg -n '^[[:space:]]*describe(\.[a-z]+)?\(' "$f" 2>/dev/null)
  (( ${#starts[@]} )) || return 0
  for ((i = 0; i < ${#texts[@]}; i++)); do
    indent="${texts[i]%%[![:space:]]*}"
    indents[i]=${#indent}
  done
  eof=$(wc -l < "$f")

  # Depth-1 helper table: module-level declarations (column 0) a describe block
  # may be delegating its construction to. A helper's body runs from its
  # declaration to whichever comes first — the next module-level declaration or
  # the first describe below it. Both bounds are load-bearing: without the
  # describe bound, the last helper in a file swallows every test below it and
  # every symbol resolves, which is a silent total no-op.
  local -a hnames=() hbegs=() hends=()
  local hl ln txt k stop
  while IFS= read -r hl; do
    ln="${hl%%:*}"; txt="${hl#*:}"
    [[ "$txt" =~ (function|const|let|var|class)[[:space:]]+([A-Za-z_\$][A-Za-z0-9_\$]*) ]] || continue
    [[ ${#BASH_REMATCH[2]} -ge 3 ]] || continue
    hnames+=("${BASH_REMATCH[2]}"); hbegs+=("$ln")
  done < <(rg -n '^(?:export[[:space:]]+)?(?:default[[:space:]]+)?(?:async[[:space:]]+)?(?:function|const|let|var|class)[[:space:]]' "$f" 2>/dev/null)

  # Depth-1 across files, for TEST HELPERS ONLY: binding -> the helper file it
  # came from. Measured: `describe('defineInProcessApp')` over a block that only
  # calls `makeInProcessSource` from `test/helpers/`, which is where the platform
  # put the construction when it replaced the old constructor. Same-file inlining
  # cannot see it.
  #
  # The helper-path restriction is what keeps this from gutting the check. Inline
  # any imported source file and a block that calls a NEIGHBOURING function from
  # the subject's own module clears on that module's text — which is precisely
  # one of the two shapes B exists to catch. Test-support files carry no such
  # risk: nothing in the suite is "about" them.
  local -a ibinds=() ifiles=()
  local stmt spec binds b rf
  while IFS= read -r stmt; do
    spec="${stmt%[\"\'\`]*}"; spec="${spec##*[\"\'\`]}"
    [[ "$spec" == .* ]] || continue
    rf=$(ts_resolve "$(dirname "$f")" "$spec")
    [[ -n "$rf" ]] || continue
    # Test-support files only, matched on the NORMALIZED path (see norm_path).
    printf '%s\n' "$rf" | while IFS= read -r k; do norm_path "$k"; done \
      | grep -Ei 'helper|fixture|mock|test-util|testutil|(^|/)(__)?(tests?|specs?)(__)?/' >/dev/null || continue
    binds="${stmt#*import}"; binds="${binds%%from*}"
    binds="${binds//[\{\}]/ }"; binds="${binds//\*/ }"
    for b in ${binds//,/ }; do
      [[ "$b" =~ ^[A-Za-z_\$][A-Za-z0-9_\$]*$ ]] || continue
      [[ "$b" == as || "$b" == type || "$b" == default ]] && continue
      ibinds+=("$b"); ifiles+=("$rf")
    done
  done < <(awk '/^[[:space:]]*import[[:space:]]/ {
                  acc = $0
                  while (acc !~ /from[[:space:]]*["'"'"'`]/ && (getline nxt) > 0) acc = acc " " nxt
                  print acc
                }' "$f" 2>/dev/null)

  for ((i = 0; i < ${#hnames[@]}; i++)); do
    stop=$eof
    (( i + 1 < ${#hbegs[@]} )) && stop=$(( hbegs[i+1] - 1 ))
    for k in "${starts[@]}"; do
      if (( k > hbegs[i] )); then (( k - 1 < stop )) && stop=$(( k - 1 )); break; fi
    done
    hends[i]=$stop
  done

  for ((i = 0; i < ${#starts[@]}; i++)); do
    start=${starts[i]}
    line="${texts[i]}"

    # A block's body ends at the next describe indented no further than it is.
    # Nested describes therefore stay INSIDE their parent's body, which makes the
    # parent clear easily — deliberate, matching B's under-report-rather-than-
    # cry-wolf stance.
    end=$eof
    local j
    for ((j = i + 1; j < ${#starts[@]}; j++)); do
      if (( indents[j] <= indents[i] )); then end=$(( starts[j] - 1 )); break; fi
    done

    [[ "$line" =~ describe(\.[a-z]+)?\([[:space:]]*[\'\"\`]([^\'\"\`]+) ]] || continue
    raw="${BASH_REMATCH[2]}"

    # Conventional decorations around an otherwise bare identifier.
    sym="${raw#\#}"; sym="${sym#.}"; sym="${sym%()}"; sym="${sym%\(\)}"
    TS_BLOCKS=$((TS_BLOCKS + 1))
    [[ "$sym" =~ ^[A-Za-z_$][A-Za-z0-9_$]*$ ]] || continue
    [[ ${#sym} -ge 4 ]] || continue
    printf '%s\n' "$syms" | grep -xF -- "$sym" >/dev/null || continue
    TS_ELIGIBLE=$((TS_ELIGIBLE + 1))

    body=$(sed -n "$(( start + 1 )),${end}p" "$f")

    # Inline any module-level helper this block calls (depth 1), the same
    # concession check_b makes for Go and Python. Measured: on a real suite this
    # was the cause of EVERY residual false positive — TS tests overwhelmingly
    # construct their subject in a `freshStore()` / `makeSut()` factory declared
    # above the describe, so the block calls the helper and the symbol itself
    # appears only in the helper's body.
    local hi
    for ((hi = 0; hi < ${#hnames[@]}; hi++)); do
      printf '%s\n' "$body" | grep -F -- "${hnames[hi]}" >/dev/null || continue
      body+=$'\n'$(sed -n "${hbegs[hi]},${hends[hi]}p" "$f")
    done

    # Same concession across the file boundary, for imported test helpers.
    local ii
    for ((ii = 0; ii < ${#ibinds[@]}; ii++)); do
      printf '%s\n' "$body" | grep -F -- "${ibinds[ii]}" >/dev/null || continue
      # shellcheck disable=SC2086  # deliberate split: the value is a file list
      body+=$'\n'$(cat ${ifiles[ii]} 2>/dev/null)
    done

    if ! references_in_body_ci "$sym" "$body"; then
      finding "B" "$f:${start}: describe('$raw') never calls '$sym'" \
        "The block is named for a symbol its own body does not mention." \
        "Typical causes: it reimplements the logic locally and asserts on its own" \
        "variables, or it exercises a NEIGHBOURING function — note that other" \
        "describe blocks in this file may well exercise '$sym'."
    fi
  done
}

# Walk each test function's body. A body runs from its declaration to the next
# top-level declaration (or EOF) — the same boundary in Go and Python.
check_b() {
  local f="$1" lang="$2" starts eof i start end line name sym strip syms
  strip='[A-Z]*'; [[ "$lang" == py ]] && strip='_*'
  syms=$(declared_symbols "$f" "$lang")

  # See check_b_ts: no mapfile. It does not exist in the bash 3.2 macOS ships,
  # and its absence under `set -u` leaves `starts` empty, which reads as a clean
  # suite rather than as a check that never ran.
  local sl
  starts=()
  while IFS= read -r sl; do starts+=("$sl"); done \
    < <(rg -n '^[[:space:]]*(func |(async )?def |class )' "$f" 2>/dev/null | cut -d: -f1)
  (( ${#starts[@]} )) || return 0
  eof=$(wc -l < "$f")

  # Pass 1 — every declaration in the file with its body range, so a test that
  # delegates to a local helper can be resolved rather than reported. Three of
  # the four residual false positives on a real suite were one-line wrappers
  # around `assertXInvalid(t, ...)`, and the helper is where the call lives.
  local -a dname dbeg dend
  for ((i = 0; i < ${#starts[@]}; i++)); do
    start=${starts[i]}
    end=$eof
    (( i + 1 < ${#starts[@]} )) && end=$(( starts[i+1] - 1 ))
    line=$(sed -n "${start}p" "$f")
    if [[ "$line" =~ ^func\ (\([^\)]*\)[[:space:]]*)?([A-Za-z_][A-Za-z0-9_]*) ]]; then
      dname[i]="${BASH_REMATCH[2]}"
    elif [[ "$line" =~ def\ ([A-Za-z_][A-Za-z0-9_]*) ]]; then
      dname[i]="${BASH_REMATCH[1]}"
    else
      dname[i]=""
    fi
    dbeg[i]=$(( start + 1 )); dend[i]=$end
  done

  local j body
  for ((i = 0; i < ${#starts[@]}; i++)); do
    name="${dname[i]}"
    if [[ "$lang" == go ]]; then
      [[ "$name" == Test* ]] || continue
      sym="${name#Test}"; sym="${sym%%_*}"
    else
      [[ "$name" == test_* ]] || continue
      sym="${name#test_}"
    fi
    [[ ${#sym} -ge 4 ]] || continue

    # Only a name that IS a declared symbol can be "the subject this test forgot
    # to call". A topic prefix is not a finding — it is a naming convention.
    printf '%s\n' "$syms" | grep -xF -- "$sym" >/dev/null || continue

    body=$(sed -n "${dbeg[i]},${dend[i]}p" "$f")
    # Inline the body of any same-file helper this test calls (depth 1 — deeper
    # chains are rare enough that the extra greps buy less than they cost).
    for ((j = 0; j < ${#starts[@]}; j++)); do
      (( j == i )) && continue
      [[ -n "${dname[j]}" ]] || continue
      [[ "${dname[j]}" == Test* || "${dname[j]}" == test_* ]] && continue
      printf '%s\n' "$body" | grep -F -- "${dname[j]}" >/dev/null || continue
      body+=$'\n'$(sed -n "${dbeg[j]},${dend[j]}p" "$f")
    done

    if ! subject_referenced "$sym" "$body" "$strip"; then
      finding "B" "$f:${starts[i]}: '$name' never calls '$sym' (or any prefix of it)" \
        "The test is named for a symbol its own body does not mention." \
        "Typical causes: it reimplements the logic locally and asserts on its own" \
        "variables, or it calls a NEIGHBOURING function — note that other tests in" \
        "this same file may well exercise '$sym', which is why this is per-function."
    fi
  done
}

# C: an asserted string literal that is a verbatim fragment of nearby source.
# A guard whose predicate is source text is bypassed by any rename.
check_c() {
  local f="$1" dir lit
  dir=$(dirname "$f")

  # A string-matched guard has one defining property: it reads SOURCE CODE AS
  # DATA and asserts on the text. Without this precondition the check fires on
  # every import path and every fixture string that happens to appear in both a
  # test and a source file — ~50 findings on a healthy 31-file suite, all noise.
  # With it, the check means what its name says.
  # NOT a bare ReadFile — tests read fixture files constantly. The path being read
  # has to BE source code.
  rg -q -e 'go/parser' -e 'go/ast' -e 'inspect\.getsource' -e 'ast\.parse' \
        -e 'go:embed' -e '"[^"]*\.(go|py|ts|tsx|js|jsx|rb|rs)"' "$f" 2>/dev/null || {
    C_SKIPPED=$((C_SKIPPED + 1)); return 0
  }

  while IFS= read -r lit; do
    # Only code-shaped literals can be a source fragment; skip prose and short tokens.
    [[ ${#lit} -ge 6 ]] || continue
    case "$lit" in *[=\<\>\!+\*/\(\).-]*) ;; *) continue ;; esac
    # An import path is code-shaped but is not a guard predicate: it is how the
    # test declares a dependency it shares with the file under test.
    case "$lit" in *' '*) ;; */*) continue ;; esac
    # Does it appear verbatim in a NON-test file beside it?
    if rg -q --fixed-strings --glob '!*_test.*' --glob '!*.test.*' --glob '!*.spec.*' \
         -- "$lit" "$dir" 2>/dev/null; then
      finding "C" "$f: asserts on the literal source text \"$lit\"" \
        "That string appears verbatim in a source file in $dir." \
        "This guard checks TEXT, not behavior: renaming a local or reformatting the" \
        "expression bypasses it while the suite stays green. Anchor on the operand" \
        "(a regex over the meaningful token) instead of the whole expression."
    fi
  done < <(rg --no-filename -o -r '$1' '"([^"\\]{6,80})"' "$f" 2>/dev/null | sort -u)
}

# ---------------------------------------------------------------- dispatch
case "${1:-}" in
  cmd)   [[ $# -ge 2 ]] || { echo "usage: $0 cmd '<test command>'"; exit 2; }
         check_cmd "$2" ;;
  files) [[ $# -ge 2 ]] || { echo "usage: $0 files <test-file>..."; exit 2; }
         shift; check_files "$@" ;;
  both)  [[ $# -ge 3 ]] || { echo "usage: $0 both '<cmd>' <test-file>..."; exit 2; }
         check_cmd "$2"; shift 2; check_files "$@" ;;
  *)     echo "usage: $0 {cmd '<test command>' | files <test-file>... | both '<cmd>' <file>...}"; exit 2 ;;
esac

printf '\n--- vacuous-green pre-flight: what was actually checked ---\n'
for c in "${CHECKED[@]}"; do note "$c"; done
printf '\n%d suspect finding(s). This detects three known shapes; it does not prove a\nsuite is non-vacuous. Read the coverage list above before reporting a pass.\n' "$FINDINGS"

(( FINDINGS == 0 )) || exit 1
