#!/usr/bin/env bash
# clone-block-scan — find copy-pasted blocks across a tree.
#
# Why this exists: the most common structural defect a phase-bound review cannot
# see is a block that phase 4 copied out of phase 2. Each diff is individually
# fine — the copy is new code in the diff under review, and the original is in a
# file that diff never touches. Only a whole-tree view can pair them, and by the
# time anyone takes one the branch is done.
#
# What it finds, stated honestly: VERBATIM and near-verbatim duplication, after
# whitespace and comments are normalized away. Identifiers are NOT normalized, so
# a block that was copied and then renamed will not match. That is deliberate —
# every hit is a genuine copy a reader can confirm in seconds, rather than a
# similarity score to argue with.
#
# What it does NOT find: the same concept implemented twice from scratch —
# two independent mean calculations whose zero-guards have already drifted, one
# rule enforced on both sides of a client/server boundary. Those are the other
# half of the problem and they need a reader, not a hash. Do not read a clean
# scan as "no duplication".
#
# Report-only. Nothing here is a defect on its own: a repeated three-line
# assertion setup may be the clearest way to write it.
#
# Usage: clone-block-scan.sh <dir> [--min-lines N]   (default N=6)
#
# Exit codes:
#   0  ran successfully (findings or not — read the report)
#   2  USAGE — bad invocation or missing dependency; DID NOT RUN

set -uo pipefail

die_usage() {
  printf 'clone-block-scan: USAGE ERROR — %s\n' "$1" >&2
  printf 'The scan DID NOT RUN. Absence of findings here means nothing.\n' >&2
  exit 2
}

[ $# -ge 1 ] || die_usage "expected a directory to scan"
DIR="$1"; shift
[ -d "$DIR" ] || die_usage "not a directory: $DIR"
command -v rg  >/dev/null 2>&1 || die_usage "rg (ripgrep) is required and was not found"
command -v awk >/dev/null 2>&1 || die_usage "awk is required and was not found"

MIN=6
while [ $# -gt 0 ]; do
  case "$1" in
    --min-lines) shift; [ $# -ge 1 ] || die_usage "--min-lines needs a value"; MIN="$1" ;;
    *) die_usage "unknown option: $1" ;;
  esac
  shift
done
case "$MIN" in ''|*[!0-9]*) die_usage "--min-lines must be a positive integer" ;; esac
[ "$MIN" -ge 3 ] || die_usage "--min-lines below 3 reports noise, not clones"

cd "$DIR" || die_usage "cannot enter $DIR"

# Test files are IN scope. A large share of real duplication lives in fixture
# seeding and table scanners copied between test files, and it drifts the same
# way production code does.
FILES=$(rg -l --type go --type ts --type js --type py --type cs --type css '' 2>/dev/null \
  | rg -v '(^|/)(node_modules|vendor|dist|build|\.next|__snapshots__)/' || true)
[ -n "$FILES" ] || die_usage "no Go/TS/JS/Python/C#/CSS sources found under $DIR"

NFILES=$(printf '%s\n' "$FILES" | rg -c . || printf '0')

printf '%s\n' "$FILES" | awk -v MIN="$MIN" '
# ---- normalize ---------------------------------------------------------------
# Drop comments and blank lines; collapse whitespace; drop lines too short to
# carry meaning. Punctuation-only lines ("}", "})", ");") match everywhere and
# would glue unrelated blocks into one giant false clone.
# Import blocks are the loudest false positive there is: two files importing the
# same four packages are not a clone, and the block sits at the top of every file
# so it pairs with everything. Uses `inimp`, which the read loop resets per file.
function skip_import(s,   t) {
  t = s
  gsub(/^[ \t]+|[ \t]+$/, "", t)
  if (inimp) {                                  # inside a multi-line import
    if (t ~ /^\)/ || t ~ /from ['"'"'"]/ || t ~ /^$/) inimp = 0
    return 1
  }
  if (t ~ /^import[ \t]*\($/) { inimp = 1; return 1 }        # Go block form
  if (t ~ /^import[ \t]*\{$/) { inimp = 1; return 1 }        # TS multi-line
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

# ---- pass 1: read every file into significant-line arrays --------------------
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
    src[nf, i] = ln          # original 1-indexed line number
  }
  close(f)
  cnt[nf] = i
  ln = 0
}

END {
  # ---- build windows ---------------------------------------------------------
  # key = MIN consecutive significant lines joined. Identical keys are identical
  # code after normalization.
  for (a = 1; a <= nf; a++) {
    for (i = 1; i + MIN - 1 <= cnt[a]; i++) {
      k = ""
      for (j = 0; j < MIN; j++) k = k "\001" txt[a, i + j]
      occ[k] = occ[k] " " a ":" i
      n_occ[k]++
    }
  }

  # ---- pair windows into clone edges -----------------------------------------
  # Two occurrences of one key are a clone pair. Consecutive windows of the SAME
  # clone share one (fileA, fileB, offset) triple — that is what lets adjacent
  # windows merge back into a single block instead of MIN-line confetti.
  for (k in occ) {
    if (n_occ[k] < 2) continue
    m = split(occ[k], w, " ")
    for (p = 1; p <= m; p++) {
      if (w[p] == "") continue
      split(w[p], A, ":")
      for (q = p + 1; q <= m; q++) {
        if (w[q] == "") continue
        split(w[q], B, ":")
        fa = A[1]+0; ia = A[2]+0; fb = B[1]+0; ib = B[2]+0
        # Same file: only count non-overlapping repeats.
        if (fa == fb && (ib - ia) < MIN) continue
        if (fa == fb && ia > ib) { t = ia; ia = ib; ib = t }
        if (fa > fb) { t = fa; fa = fb; fb = t; t = ia; ia = ib; ib = t }
        e = fa SUBSEP fb SUBSEP (ib - ia)
        starts[e] = starts[e] " " ia
      }
    }
  }

  # ---- merge consecutive windows into blocks ---------------------------------
  nb = 0
  for (e in starts) {
    m = split(starts[e], s, " ")
    d = 0
    for (p = 1; p <= m; p++) if (s[p] != "") { d++; v[d] = s[p]+0 }
    if (d == 0) continue
    # sort + dedupe
    for (p = 2; p <= d; p++) { x = v[p]; q = p - 1
      while (q >= 1 && v[q] > x) { v[q+1] = v[q]; q-- } ; v[q+1] = x }
    split(e, E, SUBSEP)
    fa = E[1]+0; fb = E[2]+0; off = E[3]+0
    run_start = v[1]; prev = v[1]
    for (p = 2; p <= d + 1; p++) {
      cur = (p <= d) ? v[p] : -1
      if (cur == prev || cur == prev + 1) { prev = cur; continue }
      nb++
      emit(fa, fb, off, run_start, prev)
      if (cur == -1) break
      run_start = cur; prev = cur
    }
  }

  # ---- collapse clusters and report ------------------------------------------
  # One block copied to five sites is ONE finding, not ten pairs. Pairwise output
  # grows quadratically in the number of copies, so the worst duplication in the
  # tree becomes the least readable row in the report — exactly backwards.
  nc = 0
  for (ct in sites) { nc++; cl[nc] = ct; cs[nc] = clen[ct] }
  for (p = 2; p <= nc; p++) { xs = cs[p]; xr = cl[p]; q = p - 1
    while (q >= 1 && cs[q] < xs) { cs[q+1] = cs[q]; cl[q+1] = cl[q]; q-- }
    cs[q+1] = xs; cl[q+1] = xr }

  # A shorter cluster whose every site sits inside a longer cluster'"'"'s site is the
  # same finding seen through a smaller window. Report the longest form only.
  nshown = 0
  for (p = 1; p <= nc; p++) {
    if (contained(p)) continue
    nshown++
    show[nshown] = p
  }

  printf "clone-block-scan: %d file(s), min %d significant lines\n\n", nf, MIN
  if (nshown == 0) {
    print "No verbatim clone blocks at this threshold."
    print ""
  } else {
    printf "CLONE BLOCKS (%d) — normalized-identical, largest first.\n", nshown
    print  "Read each against the change map: the ones that matter are blocks whose"
    print  "copies were written by different phases, because no diff review saw both."
    print  ""
    for (p = 1; p <= nshown; p++) {
      idx = show[p]
      m = split(sites[cl[idx]], S, " ")
      ns = 0; for (q = 1; q <= m; q++) if (S[q] != "") ns++
      printf "  %d lines × %d sites\n", cs[idx], ns
      for (q = 1; q <= m; q++) {
        if (S[q] == "") continue
        split(S[q], T, ":")
        printf "      %s:%d-%d\n", fname[T[1]+0], T[2]+0, T[3]+0
      }
      print ""
    }
  }
}

# contained(): true if every site of cluster p lies inside a site of some longer
# cluster. cl[] is sorted longest-first, so only earlier clusters can contain p.
function contained(p,   m, S, q, j, k, R, r, ok, hit) {
  m = split(sites[cl[p]], S, " ")
  for (j = 1; j < p; j++) {
    if (cs[j] <= cs[p]) continue
    ok = 1
    for (q = 1; q <= m; q++) {
      if (S[q] == "") continue
      split(S[q], T2, ":")
      hit = 0
      k = split(sites[cl[j]], R, " ")
      for (r = 1; r <= k; r++) {
        if (R[r] == "") continue
        split(R[r], T3, ":")
        if (T3[1]+0 == T2[1]+0 && T3[2]+0 <= T2[2]+0 && T3[3]+0 >= T2[3]+0) { hit = 1; break }
      }
      if (!hit) { ok = 0; break }
    }
    if (ok) return 1
  }
  return 0
}

# emit(): record one merged block into its cluster, in ORIGINAL line numbers.
function emit(fa, fb, off, rs, re,   la1, la2, lb1, lb2, len, ct, j, sa, sb) {
  len = (re - rs) + MIN
  la1 = src[fa, rs]; la2 = src[fa, re + MIN - 1]
  lb1 = src[fb, rs + off]; lb2 = src[fb, re + off + MIN - 1]
  ct = ""
  for (j = rs; j <= re + MIN - 1; j++) ct = ct "\001" txt[fa, j]
  clen[ct] = len
  sa = fa ":" la1 ":" la2
  sb = fb ":" lb1 ":" lb2
  if (!((ct SUBSEP sa) in seensite)) { seensite[ct SUBSEP sa] = 1; sites[ct] = sites[ct] " " sa }
  if (!((ct SUBSEP sb) in seensite)) { seensite[ct SUBSEP sb] = 1; sites[ct] = sites[ct] " " sb }
}
'

cat <<'CAVEATS'
These are CANDIDATES, and duplication is not automatically a defect.
Ask of each pair, in this order:
  1. Have the two copies already DRIFTED? A pair that must stay word-identical
     and is maintained by hand is the failure mode, whether or not it has bitten
     yet. Diff them before deciding.
  2. Were they written by DIFFERENT phases? Then no diff review could have seen
     the pair, and this scan is the only thing that will.
  3. Would extracting cost more than it saves? Repeated test setup and adjacent
     literal assertions are often clearest left alone. Say so and move on.

Known limits — do NOT read a clean scan as "no duplication":
  - Identifiers are not normalized: a copy that was renamed does not match.
  - Same concept implemented twice from scratch never matches at all. That class
    (two mean calculations, one rule enforced client and server) is invisible
    here and needs a reader.
  - Whole-file clones of generated or vendored code may be legitimate.
CAVEATS
exit 0
