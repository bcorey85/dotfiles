#!/usr/bin/env bash
# PreToolUse hook (Write|Edit|MultiEdit|NotebookEdit): test-ownership-gate —
# implementing coders never write test files.
#
# Why this exists: under the coder/test-writer split, test authorship belongs
# to the implementation-blind test-writer. As a prose rule ("Tests Are Not
# Yours") coders still edited *_test.go 25 times in LOOP-COST round 5.
# Authority lives in enforcement (cross-round law), so the rule now lives
# here. PreToolUse input carries agent_type for subagent calls (verified
# 2026-08-03), so the deny can target exactly the coder agent types.
#
# Scope, stated honestly:
#   - Binds ONLY the implementing coder types listed below (which includes
#     review-loop's fix coders — a fix that must change a test routes through
#     the test-writer instead, per /code's test-intent routing). Main session,
#     the test-writer, reviewers, and every other agent pass through.
#   - Mechanical compile-fixes to existing tests are NOT an exception any
#     more: the coder reports them and the test-writer applies them
#     (coder-core "Tests Are Not Yours" carries the wording).
#   - acceptance-contract-gate is separate and stricter (marker-based,
#     binds everyone incl. main session); this gate is pattern-based and
#     agent-scoped. Both run; either deny stands.
#   - Shell writes (>, sed -i, tee) are write-edit-safety-gate's surface and
#     the global "file changes go through Write/Edit" rule; displacement
#     there is measured, not silently permitted.
#
# Contract (omp bridge consumes this): hook JSON on stdin; empty output =
# allow; permissionDecision JSON on stdout = deny; CLAUDE_SKIP_HOOKS escape.

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0

INPUT=$(cat)
[ -z "$INPUT" ] && exit 0

command -v jq >/dev/null 2>&1 || exit 0

AGENT=$(printf '%s' "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null)
case "$AGENT" in
  coder|backend-coder|frontend-coder|coder-deep|backend-coder-deep|frontend-coder-deep) ;;
  *) exit 0 ;;
esac

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

# Test-file patterns (mirror test-edit-telemetry.sh).
case "$FILE" in
  *_test.go|*.test.ts|*.test.tsx|*.test.js|*.test.jsx|*_spec.rb|*/test_*.py|*/tests/*.py|*.spec.ts|*.spec.js) ;;
  *) exit 0 ;;
esac

REASON="test-ownership-gate: you are an implementing coder and $FILE is a test file — test authorship belongs to the test-writer agent, dispatched after you return (coder-core: Tests Are Not Yours). This includes mechanical compile-fixes a signature change forces on existing test callers: list each needed fix in your report (file, symbol, old→new) and the test-writer applies it. If your implementation makes an existing test red for a behavioral reason, report that too; never adjust either side to green. Do not route around this via shell writes — that is the same edit with a worse audit trail."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$REASON"
exit 0
