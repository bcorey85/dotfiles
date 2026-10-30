#!/usr/bin/env bash
# Lints first (tests/lint.sh; a missing ruff stops the run), then checks for duplicate code, then runs every unit test
# under tests/, one process per test file, nproc at a time. The tests run even when the lint fails. A failed step is
# named on the last line ("FAILED: lint tests"), after the test summary, and the exit is non-zero.
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

testStatus=0
python3 "$repoRoot/tests/parallel_tests.py" || testStatus=1

failedSteps=()
[ "$lintStatus" -eq 0 ] || failedSteps+=(lint)
[ "$duplicateStatus" -eq 0 ] || failedSteps+=(duplicate-check)
[ "$testStatus" -eq 0 ] || failedSteps+=(tests)

if [ "${#failedSteps[@]}" -gt 0 ]; then
    echo "FAILED: ${failedSteps[*]}"
    exit 1
fi
