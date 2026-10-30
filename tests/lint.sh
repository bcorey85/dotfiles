#!/usr/bin/env bash
# The one lint entry point: tests/run.sh and a coder both call it.
#   bash tests/lint.sh                 the whole lint of the suite
#   bash tests/lint.sh <file.py>...    only those files: ruff check on each, and the complexity gate on the ones
#                                      among them that are code-step or review-flow files; other arguments are skipped,
#                                      except review/verify-log and review/verify-prep, which have no .py suffix
# The whole lint is the ruff rules in ruff.toml (a failure) and a C901 complexity report (not a failure), then the C901
# gate on the code-step and review-flow files (a failure).
# Exit: 0 clean, 1 a lint failure, 2 ruff is not installed (run.sh stops the run on 2).
set -euo pipefail

callerDir="$PWD"
repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

if ! command -v ruff >/dev/null 2>&1; then
    echo "ruff not installed: install it (pacman -S ruff, brew install ruff or pipx install ruff) and rerun" >&2
    exit 2
fi

codeStepFiles=(claude/.claude/scripts/code/code_step.py claude/.claude/scripts/code/code_step_core.py
    claude/.claude/scripts/code/code_step_hooks.py claude/.claude/scripts/code/code_step_boundary.py
    claude/.claude/scripts/code/code_step_verification.py claude/.claude/scripts/code/code_step_closing.py
    claude/.claude/scripts/code/code_step_gates.py claude/.claude/scripts/code/code_step_start.py
    claude/.claude/scripts/code/code_step_report.py claude/.claude/scripts/code/code_step_review.py
    claude/.claude/scripts/code/code_step_review_stops.py claude/.claude/scripts/code/code_step_state.py
    claude/.claude/scripts/code/code_step_routes.py claude/.claude/scripts/lib/plan_format.py)
reviewFlowFiles=(claude/.claude/scripts/review/review_fix.py claude/.claude/scripts/review/handback.py
    claude/.claude/scripts/review/review_loop_gate.py claude/.claude/scripts/review/review_commit_gate.py
    claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_findings.py
    claude/.claude/scripts/review/review_loop_packet.py claude/.claude/scripts/review/review_loop_closure.py
    claude/.claude/scripts/review/full_check_gate.py claude/.claude/scripts/review/full_check.py
    claude/.claude/scripts/review/handback_store.py claude/.claude/scripts/review/saved_handback.py
    claude/.claude/scripts/review/finding_record.py claude/.claude/scripts/lib/loop_transcript.py)
gatedFiles=("${codeStepFiles[@]}" "${reviewFlowFiles[@]}")

lintStatus=0

if [ "$#" -eq 0 ]; then
    ruff check --no-cache claude/.claude/scripts claude/.claude/skills tests/scripts tests/duplicate_code.py || lintStatus=1
    ruff check --no-cache --select C901 --output-format concise claude/.claude/scripts || echo "complexity report only: not a failure" >&2
    ruff check --no-cache --select C901 "${gatedFiles[@]}" || lintStatus=1
    exit "$lintStatus"
fi

# Relative arguments are the caller's: resolve them against the caller's folder, since the lint runs from the root.
givenFiles=()
givenGatedFiles=()
for givenFile in "$@"; do
    case "$givenFile" in
        /*) givenAbsolute="$(realpath -m "$givenFile")" ;;
        *) givenAbsolute="$(realpath -m "$callerDir/$givenFile")" ;;
    esac
    givenRelative="$(realpath -m --relative-to="$repoRoot" "$givenAbsolute")"
    case "$givenRelative" in
        *.py | claude/.claude/scripts/review/verify-log | claude/.claude/scripts/review/verify-prep) ;;
        *) continue ;;
    esac
    givenFiles+=("$givenAbsolute")
    for gatedFile in "${gatedFiles[@]}"; do
        if [ "$givenRelative" = "$gatedFile" ]; then
            givenGatedFiles+=("$givenAbsolute")
            break
        fi
    done
done

if [ "${#givenFiles[@]}" -eq 0 ]; then
    exit 0
fi

ruff check --no-cache "${givenFiles[@]}" || lintStatus=1
if [ "${#givenGatedFiles[@]}" -gt 0 ]; then
    ruff check --no-cache --select C901 "${givenGatedFiles[@]}" || lintStatus=1
fi
exit "$lintStatus"
