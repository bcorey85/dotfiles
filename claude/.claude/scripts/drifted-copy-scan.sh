#!/usr/bin/env bash
# drifted-copy-scan — find blocks that were copies and have since DIVERGED.
#
# Why this is a separate scan from clone-block-scan, and not a flag on it:
# they are opposites in the one way that matters. clone-block-scan finds copies
# that still match, and a matching pair is a maintenance smell — real, but not
# yet wrong. This scan finds pairs that no longer match, and those are the ones
# that have already bitten. A copied validator whose two halves agree is tidy
# debt; the same validator after one side tightened a bound is a live defect on
# whichever side was forgotten.
#
# The perverse consequence, which is the entire reason this exists: an exact-match
# clone detector goes BLIND at exactly the moment the pair becomes a bug. While
# the copies agree it reports them; the edit that breaks them apart also deletes
# them from its output. So the one signal you most want is the one signal a
# clone scan structurally cannot emit.
#
# How it decides, with no similarity score to argue with: a window of N
# significant lines is keyed N times, once with each line masked out. Two windows
# that collide on a masked key are identical in N-1 of N lines and differ in the
# remaining one. There is no threshold and no tuning knob — either N-1 lines are
# byte-identical after normalization or they are not. A pair that differs in two
# or more lines is NOT reported; that is a deliberate floor, because by then the
# blocks may simply be different code and the evidence for "these were once one
# thing" is gone.
#
# Output is the differing LINE PAIR, not the block. Two 40-line functions that
# diverge at one line produce one row naming that line on both sides, because
# that line is the whole finding and the surrounding 39 are the proof.
#
# What it does NOT find, stated plainly:
#   - copies that drifted in two or more lines (see the floor above)
#   - copies that were renamed (identifiers are not normalized, same as the
#     clone scan)
#   - the same rule implemented twice from scratch, which never matched at all
# A clean run here means "no single-line divergences", not "the copies agree".
#
# Test files are EXCLUDED by default, which is the one place this scan and
# clone-block-scan deliberately disagree. The reason is semantic, not a threshold
# that was tuned until the output looked nice: "identical in N-1 of N lines" means
# opposite things in the two contexts. In production code it is anomalous and
# almost always a copy. In test code it is the ordinary idiom — a parameterized
# case written out longhand, where differing in exactly one field is the POINT.
# Measured on one real repo: 146 findings, of which 137 came from two test files
# and none of those were defects. Pass --include-tests when auditing test helpers
# specifically, and expect to read past that idiom yourself.
#
# Usage: drifted-copy-scan.sh <dir> [--min-lines N] [--include-tests]   (default N=6)
#
# Exit codes:
#   0  ran successfully (findings or not — read the report)
#   2  USAGE — bad invocation or missing dependency; DID NOT RUN

set -uo pipefail

die_usage() {
  printf 'drifted-copy-scan: USAGE ERROR — %s\n' "$1" >&2
  printf 'The scan DID NOT RUN. Absence of findings here means nothing.\n' >&2
  exit 2
}

[ $# -ge 1 ] || die_usage "expected a directory to scan"
DIR="$1"; shift
[ -d "$DIR" ] || die_usage "not a directory: $DIR"
command -v rg  >/dev/null 2>&1 || die_usage "rg (ripgrep) is required and was not found"
command -v awk >/dev/null 2>&1 || die_usage "awk is required and was not found"

MIN=6
INCLUDE_TESTS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --min-lines) shift; [ $# -ge 1 ] || die_usage "--min-lines needs a value"; MIN="$1" ;;
    --include-tests) INCLUDE_TESTS=1 ;;
    *) die_usage "unknown option: $1" ;;
  esac
  shift
done
case "$MIN" in ''|*[!0-9]*) die_usage "--min-lines must be a positive integer" ;; esac
# Below 4, a "match" is 3 identical lines around a difference. That is the shape
# of ordinary sibling code, not of a copy, and the report fills with noise.
[ "$MIN" -ge 4 ] || die_usage "--min-lines below 4 cannot evidence a copy"

cd "$DIR" || die_usage "cannot enter $DIR"

# CSS is scanned by clone-block-scan but NOT here, for the same reason tests are
# excluded: a rule block that matches another in 5 of 6 declarations and differs
# in one value is what a stylesheet IS. There is no stale side to fix.
FILES=$(rg -l --type go --type ts --type js --type py --type cs '' 2>/dev/null \
  | rg -v '(^|/)(node_modules|vendor|dist|build|\.next|__snapshots__)/' || true)
if [ "$INCLUDE_TESTS" -eq 0 ]; then
  FILES=$(printf '%s\n' "$FILES" \
    | rg -v '(\.(test|spec)\.[cm]?[jt]sx?$|_test\.go$|(^|/)test_[^/]*\.py$|[^/]*_test\.py$|Tests?\.cs$|(^|/)(tests?|__tests__)/)' || true)
  SCOPE="production sources only (--include-tests to add tests)"
else
  SCOPE="production and test sources"
fi
[ -n "$FILES" ] || die_usage "no Go/TS/JS/Python/C#/CSS sources found under $DIR"

printf '%s\n' "$FILES" | awk -v MIN="$MIN" -v SCOPE="$SCOPE" '
# Normalization is deliberately identical to clone-block-scan. The two scans
# must agree on what "the same line" means, or a pair one of them calls exact
# will show up in the other as drifted.
function skip_import(s,   t) {
  t = s
  gsub(/^[ \t]+|[ \t]+$/, "", t)
  if (inimp) {
    if (t ~ /^\)/ || t ~ /from ['"'"'"]/ || t ~ /^$/) inimp = 0
    return 1
  }
  if (t ~ /^import[ \t]*\($/) { inimp = 1; return 1 }
  if (t ~ /^import[ \t]*\{$/) { inimp = 1; return 1 }
  if (t ~ /^(import|from|require|using|use|package|namespace|#include)\b/) return 1
  if (t ~ /^(const|let|var)[^=]*=[ \t]*require\(/) return 1
  return 0
}

function norm(s,   t) {
  t = s
  gsub(/^[ \t]+|[ \t]+$/, "", t)
  gsub(/[ \t]+/, " ", t)
  if (t == "") return ""
  if (t ~ /^(\/\/|#|\*|\/\*)/) return ""
  if (length(t) < 5) return ""
  return t
}

{
  f = $0
  nf++
  fname[nf] = f
  i = 0
  inimp = 0
  while ((getline line < f) > 0) {
    ln++
    if (skip_import(line)) continue
    t = norm(line)
    if (t == "") continue
    i++
    txt[nf, i] = t
    src[nf, i] = ln
  }
  close(f)
  cnt[nf] = i
  ln = 0
}

END {
  # ---- leave-one-out keying --------------------------------------------------
  # Window (a,i) contributes MIN keys: for each masked position d, the window
  # text with line i+d replaced by a sentinel. A collision on such a key means
  # the two windows agree on MIN-1 lines and disagree at d.
  for (a = 1; a <= nf; a++) {
    for (i = 1; i + MIN - 1 <= cnt[a]; i++) {
      for (d = 0; d < MIN; d++) {
        k = d
        for (j = 0; j < MIN; j++)
          k = k "\001" ((j == d) ? "\002" : txt[a, i + j])
        loo[k] = loo[k] " " a ":" i
        nloo[k]++
      }
    }
  }

  nfind = 0
  for (k in loo) {
    if (nloo[k] < 2) continue
    split(k, KD, "\001")
    d = KD[1] + 0
    m = split(loo[k], w, " ")
    for (p = 1; p <= m; p++) {
      if (w[p] == "") continue
      split(w[p], A, ":")
      for (q = p + 1; q <= m; q++) {
        if (w[q] == "") continue
        split(w[q], B, ":")
        fa = A[1]+0; ia = A[2]+0; fb = B[1]+0; ib = B[2]+0

        # Overlapping windows in one file share lines by construction; a
        # difference between them is the file being read against itself.
        if (fa == fb && (ia > ib ? ia - ib : ib - ia) < MIN) continue

        la = txt[fa, ia + d]; lb = txt[fb, ib + d]
        # Equal here means the windows are an EXACT clone that happens to
        # collide on a masked key too. That pair belongs to clone-block-scan,
        # and reporting it here would make every clone look like a drift.
        if (la == lb) continue

        # Key the finding by the differing LINE PAIR, not the window. Adjacent
        # overlapping windows all witness the same divergence; without this the
        # same one line reports MIN times.
        ra = src[fa, ia + d]; rb = src[fb, ib + d]
        if (fa > fb || (fa == fb && ra > rb)) {
          t = fa; fa = fb; fb = t; t = ra; ra = rb; rb = t; t = la; la = lb; lb = t
        }
        fk = fa ":" ra "\003" fb ":" rb
        if (fk in seen) continue
        seen[fk] = 1

        # Two functions that diverge in three places produce three rows here,
        # one per window position. They are ONE finding — the same aligned pair
        # of regions — so group by (fileA, fileB, alignment offset) and let the
        # report list every divergence under a single heading. Without this the
        # most-drifted pair in the tree is also the most repetitive to read.
        g = fa SUBSEP fb SUBSEP (rb - ra)
        if (!(g in gseen)) { gseen[g] = 1; ng++; glist[ng] = g }
        gdiv[g] = gdiv[g] "\004" ra "\005" la "\005" rb "\005" lb
        gn[g]++
        nfind++
      }
    }
  }

  printf "drifted-copy-scan: %d file(s), %s\n", nf, SCOPE
  printf "%d identical lines required around each difference\n\n", MIN - 1
  if (ng == 0) {
    print "No single-line divergences between otherwise-identical blocks."
    print ""
  } else {
    printf "DRIFTED COPIES (%d pair(s), %d divergence(s)) — %d lines identical\n", ng, nfind, MIN - 1
    print  "around each difference. Each block below is ONE aligned pair of regions;"
    print  "the lines under it are where they disagree. Ask which side is correct —"
    print  "usually exactly one of them is."
    print  ""
    for (p = 1; p <= ng; p++) {
      g = glist[p]
      split(g, G, SUBSEP)
      printf "  %s  <->  %s   (%d divergence(s))\n", fname[G[1]+0], fname[G[2]+0], gn[g]
      m = split(gdiv[g], D, "\004")
      for (q = 1; q <= m; q++) {
        if (D[q] == "") continue
        split(D[q], E, "\005")
        printf "      L%-6s %s\n", E[1], E[2]
        printf "      L%-6s %s\n", E[3], E[4]
      }
      print ""
    }
  }
}
'

cat <<'CAVEATS'
These are CANDIDATES. Read each pair and ask, in this order:
  1. Is ONE SIDE WRONG? This is the common case and the reason to run this scan.
     A bound tightened on one side of a boundary, a message reworded in one of
     two handlers, a guard added to one copy. Fix the stale side.
  2. Is the difference INTENTIONAL? Two call sites that legitimately differ in
     one argument will land here. Say so and move on — but say it out loud,
     because "intentional" is also what the stale side looks like from inside.
  3. Should the block be shared at all? If one line differs, that line is usually
     the parameter and the rest is the function.

The dominant FALSE POSITIVE has one recognizable shape, so learn it and skip fast:
adjacent declaration blocks — struct fields, interface members, JSX prop lists,
parameter lists — whose lines are individually generic ("context: string,"). Five
of those align by coincidence rather than by copying. Tell them apart by reading
the two differing lines alone: a real drift is one line EDITED from the other and
they still look alike ("status: string" / "status: RunStatus"), whereas a
coincidence pairs two lines with nothing in common ("placeholder=..." /
"disabled={saving}"). Measured precision on two real repos was 7 of 8 pairs and
2 of 6 — expect to dismiss roughly half, at about two lines of reading each.

Known limits — a clean run is NOT "the copies agree":
  - Only SINGLE-line divergence is reported. Two copies that drifted in two
    places are past the evidence floor and appear nowhere.
  - Renamed copies never match; identifiers are not normalized.
  - Transitive clusters are not collapsed: one type mirrored across three files
    reports as three pairs, not one finding. Read them together.
  - Test tables and fixture rows that differ by one field are structurally
    identical to a drifted copy, which is why tests are excluded by default.
CAVEATS
exit 0
