#!/usr/bin/env bash
# Lints first (ruff with the rules in ruff.toml fails the run; C901 only reports, but fails the run in the code-step
# and review-flow files; a missing ruff stops the run), then checks for any duplicate code
# (tests/duplicate_code.py), then runs every unit test under tests/, one process per test
# file, nproc at a time. The tests run even when the lint fails. Exits non-zero on any failure.
# `REAL_PLANS=1 bash tests/run.sh` also parses every real plan under ~/dev.
set -euo pipefail

repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

# The gates under test pass everything while the session switch that turns hooks off is set.
unset CLAUDE_SKIP_HOOKS

lintStatus=0
if command -v ruff >/dev/null 2>&1; then
    ruff check --no-cache claude/.claude/scripts claude/.claude/skills tests/scripts tests/duplicate_code.py || lintStatus=1
    ruff check --no-cache --select C901 --output-format concise claude/.claude/scripts || echo "complexity report only: not a failure" >&2
    codeStepFiles=(claude/.claude/scripts/code/code_step.py claude/.claude/scripts/code/code_step_core.py
        claude/.claude/scripts/code/code_step_hooks.py claude/.claude/scripts/code/code_step_boundary.py
        claude/.claude/scripts/lib/plan_format.py)
    reviewFlowFiles=(claude/.claude/scripts/review/review_fix.py claude/.claude/scripts/review/handback.py
        claude/.claude/scripts/review/review_loop_gate.py claude/.claude/scripts/review/review_commit_gate.py)
    ruff check --no-cache --select C901 "${codeStepFiles[@]}" "${reviewFlowFiles[@]}" || lintStatus=1
else
    echo "ruff not installed: install it (pacman -S ruff, brew install ruff or pipx install ruff) and rerun" >&2
    exit 1
fi

duplicateStatus=0
python3 "$repoRoot/tests/duplicate_code.py" || duplicateStatus=1

testStatus=0
python3 "$repoRoot/tests/parallel_tests.py" || testStatus=1

if [ "$lintStatus" -ne 0 ] || [ "$duplicateStatus" -ne 0 ] || [ "$testStatus" -ne 0 ]; then
    exit 1
fi
