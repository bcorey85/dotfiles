#!/usr/bin/env bash
# The one lint entry point: tests/run.sh and a coder both call it.
#   bash tests/lint.sh                 the whole lint of the suite
#   bash tests/lint.sh <file.py>...    only those files: ruff check on each, and the complexity gate on the ones
#                                      among them that are /code or review-flow files; other arguments are skipped,
#                                      except review/verify-log and review/verify-prep, which have no .py suffix
# The whole lint is the ruff rules in ruff.toml (a failure) and a C901 complexity report (not a failure), then the C901
# gate on the /code and review-flow files (a failure). A failing run ends with `lint failed: <step> (<count>), ...`,
# where <count> is `N errors`, `1 error` or `failed, no error count`.
# Exit: 0 clean, 1 a lint failure, 2 ruff is not installed (run.sh stops the run on 2).
set -euo pipefail

callerDir="$PWD"
repoRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repoRoot"

if ! command -v ruff >/dev/null 2>&1; then
    echo "ruff not installed: install it (pacman -S ruff, brew install ruff or pipx install ruff) and rerun" >&2
    exit 2
fi

codeFlowFiles=(claude/.claude/scripts/code/plan_check.py claude/.claude/scripts/code/plan_verification.py
    claude/.claude/scripts/code/concentration.py claude/.claude/scripts/code/coder_report.py
    claude/.claude/scripts/code/coder_gate.py claude/.claude/scripts/code/code_wait.py
    claude/.claude/scripts/code/code_review_start.py claude/.claude/scripts/code/gate_commands.py
    claude/.claude/scripts/lib/plan_format.py)
reviewFlowFiles=(claude/.claude/scripts/review/review_fix.py claude/.claude/scripts/review/handback.py
    claude/.claude/scripts/lib/git_alias_commits.py claude/.claude/scripts/lib/git_commit_calls.py
    claude/.claude/scripts/review/review_loop_script.py claude/.claude/scripts/review/review_loop_main.py
    claude/.claude/scripts/review/review_loop_scoped_tests.py
    claude/.claude/scripts/review/review_loop_findings.py
    claude/.claude/scripts/review/review_loop_packet.py claude/.claude/scripts/review/review_loop_closure.py
    claude/.claude/scripts/review/full_check_gate.py claude/.claude/scripts/review/full_check.py
    claude/.claude/scripts/review/handback_store.py claude/.claude/scripts/review/saved_handback.py
    claude/.claude/scripts/review/finding_record.py claude/.claude/scripts/lib/loop_transcript.py)
gatedFiles=("${codeFlowFiles[@]}" "${reviewFlowFiles[@]}")

lintStatus=0
failedSteps=()
stepLog="$(mktemp)"
trap 'rm -f "$stepLog"' EXIT

# runStep <step name> <ruff args>...: streams ruff's output and records a failed step for finish.
runStep() {
    local stepName="$1"
    shift
    local stepExit=0
    ruff check --no-cache "$@" | tee "$stepLog" || stepExit="${PIPESTATUS[0]}"
    if [ "$stepExit" -eq 0 ]; then
        return 0
    fi
    lintStatus=1
    local errorCount
    errorCount="$(sed -n 's/^Found \([0-9][0-9]*\) errors\{0,1\}\..*/\1/p' "$stepLog" | tail -n 1)"
    case "$errorCount" in
        "") failedSteps+=("$stepName (failed, no error count)") ;;
        1) failedSteps+=("$stepName (1 error)") ;;
        *) failedSteps+=("$stepName ($errorCount errors)") ;;
    esac
}

# The C901 sites as a concise list, without ruff's "Found N errors" line, which reads like a failure.
reportComplexity() {
    local reportLines
    local reportExit=0
    reportLines="$(ruff check --no-cache --quiet --select C901 --output-format concise \
        claude/.claude/scripts)" || reportExit=$?
    # ruff exits 1 when it finds sites; any other nonzero exit means the report did not run.
    if [ "$reportExit" -gt 1 ]; then
        echo "complexity report could not run (ruff exit $reportExit): not a failure"
        return 0
    fi
    local siteCount=0
    if [ -n "$reportLines" ]; then
        echo "$reportLines"
        siteCount="$(printf '%s\n' "$reportLines" | grep -c ' C901 ' || true)"
    fi
    local siteWord="functions"
    if [ "$siteCount" -eq 1 ]; then
        siteWord="function"
    fi
    echo "complexity report only ($siteCount $siteWord over the limit): not a failure"
}

# The last line a session reads: which steps failed, so a failure never scrolls past as a pass.
finish() {
    if [ "$lintStatus" -ne 0 ]; then
        local joined
        joined="$(printf '%s, ' "${failedSteps[@]}")"
        echo "lint failed: ${joined%, }"
    fi
    exit "$lintStatus"
}

if [ "$#" -eq 0 ]; then
    runStep "ruff rules" claude/.claude/scripts claude/.claude/skills tests/scripts tests/duplicate_code.py
    reportComplexity
    runStep "complexity gate" --select C901 "${gatedFiles[@]}"
    finish
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

runStep "ruff rules" "${givenFiles[@]}"
if [ "${#givenGatedFiles[@]}" -gt 0 ]; then
    runStep "complexity gate" --select C901 "${givenGatedFiles[@]}"
fi
finish
