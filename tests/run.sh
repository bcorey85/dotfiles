#!/usr/bin/env bash
# Lints first (tests/lint.sh; a missing ruff stops the run), then checks for duplicate code, then runs every unit test
# under tests/, one process per test file, nproc at a time, then checks the real review-gate folder for new keys under
# the run's temp folder. The tests run even when the lint fails.
# A failed step (lint, duplicate-check, tests, review-gate-state) is named on the last line, and the exit is non-zero.
# `REAL_PLANS=1 bash tests/run.sh` also parses every real plan under ~/dev.
set -euo pipefail

repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

# The gates under test pass everything while the session switch that turns hooks off is set.
unset CLAUDE_SKIP_HOOKS

lintStatus=0
"$BASH" "$repoRoot/tests/lint.sh" || lintStatus=$?
lintMissingRuffStatus=2
if [ "$lintStatus" -eq "$lintMissingRuffStatus" ]; then
    exit 1
fi

duplicateStatus=0
python3 "$repoRoot/tests/duplicate_code.py" || duplicateStatus=1

gateStatus=0
gateKeys="$(python3 "$repoRoot/tests/review_gate_unchanged.py" snapshot)" || gateStatus=1

# The tests get their own temp root, so only this run's repos can trip the gate check. The slot folder stays where
# parallel_tests picks it without TMPDIR, so the machine-wide worker cap holds.
runTmp="$(mktemp -d)"
trap 'rm -rf "$runTmp"' EXIT
slotDir="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import parallel_tests; print(parallel_tests.slot_folder())' "$repoRoot/tests")"

testStatus=0
TMPDIR="$runTmp" SUITE_SLOT_DIR="$slotDir" python3 "$repoRoot/tests/parallel_tests.py" || testStatus=1

if [ "$gateStatus" -eq 0 ]; then
    python3 "$repoRoot/tests/review_gate_unchanged.py" compare "$runTmp" <<<"$gateKeys" || gateStatus=1
fi

failedSteps=()
[ "$lintStatus" -eq 0 ] || failedSteps+=(lint)
[ "$duplicateStatus" -eq 0 ] || failedSteps+=(duplicate-check)
[ "$testStatus" -eq 0 ] || failedSteps+=(tests)
[ "$gateStatus" -eq 0 ] || failedSteps+=(review-gate-state)

if [ "${#failedSteps[@]}" -gt 0 ]; then
    echo "FAILED: ${failedSteps[*]}"
    exit 1
fi
