#!/usr/bin/env bash
# PreToolUse hook (Write|Edit|MultiEdit|NotebookEdit): test-ownership-gate —
# denies test-file writes to the agent types in BOUND_AGENTS.
#
# The list is empty: implementing coders write their own tests, and every
# agent passes through. Add an agent type to re-arm the deny for it.
#
#   - Pattern-based and agent-scoped. Main session always passes.
#   - Shell writes (>, tee, sed -i, rm, mv, cp, git rm/checkout/restore) are
#     routed back through this script by shell-write-gate.sh, per target path.
#
# Contract (omp bridge consumes this): hook JSON on stdin; empty output =
# allow; permissionDecision JSON on stdout = deny; CLAUDE_SKIP_HOOKS escape.

# Read stdin before any exit: a caller piping the hook JSON in fails on a
# closed pipe when this script exits unread.
INPUT=$(cat)
[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0
[ -z "$INPUT" ] && exit 0

BOUND_AGENTS=""
[ -z "$BOUND_AGENTS" ] && exit 0

command -v jq >/dev/null 2>&1 || exit 0

AGENT=$(printf '%s' "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null)
[ -z "$AGENT" ] && exit 0
case " $BOUND_AGENTS " in
*" $AGENT "*) ;;
*) exit 0 ;;
esac

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

# Test-file patterns + fixture dirs.
case "$FILE" in
*_test.go | *.test.ts | *.test.tsx | *.test.js | *.test.jsx | *.spec.ts | *.spec.tsx | *.spec.js | *.spec.jsx | *_spec.rb | */test_*.py | *_test.py | */conftest.py) ;;
*/tests/* | */testdata/* | */fixtures/* | */__tests__/* | */__mocks__/*) ;;
*) exit 0 ;;
esac

REASON="test-ownership-gate: agent $AGENT may not write test files and $FILE is one. Report the test change you need instead. Do not route around this via shell writes — that is the same edit with a worse audit trail."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$REASON"
exit 0
