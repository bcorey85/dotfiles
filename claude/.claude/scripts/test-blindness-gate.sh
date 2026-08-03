#!/usr/bin/env bash
# PreToolUse hook (Read): test-blindness-gate — the test-writer never reads
# implementation source.
#
# Why this exists: the coder/test-writer split (LOOP-COST round 5) rests on one
# property — a test author who cannot see the implementation cannot codify its
# accidents. As a prose rule that property leaked in 21/41 measured dispatches:
# the test-writer opened non-test source with Read despite a HARD RULE saying
# not to. Authority lives in enforcement (cross-round law), so the rule now
# lives here. PreToolUse input carries agent_type/agent_id for subagent calls
# (verified 2026-08-03; the no-identity blocker in anthropics/claude-code#40140
# is resolved), which makes a per-agent read-deny finally mechanizable.
#
# Scope, stated honestly:
#   - Binds ONLY agent_type == "test-writer". Main session and every other
#     agent pass through untouched (no agent_type field on main-session calls).
#   - Denies Read of CODE files that are not tests/fixtures. Docs, plans,
#     markdown, config, test files, testdata/fixture dirs stay readable.
#   - The public surface remains available via LSP (hover, workspace symbols,
#     declarations) — LSP is not matched by this hook, deliberately: the
#     agent's contract allows declarations, and LSP cannot return bodies the
#     way Read does.
#   - Read ONLY. Bash `cat`, `git show`, and Grep displacement are left open
#     ON PURPOSE: round 8 measures whether a denied vector displaces to
#     unwatched ones (test-edit-telemetry + transcripts grade this). Do not
#     "harden" this hook without a round that measures the change.
#
# Contract (omp bridge consumes this): hook JSON on stdin; empty output =
# allow; permissionDecision JSON on stdout = deny; CLAUDE_SKIP_HOOKS escape.

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0

INPUT=$(cat)
[ -z "$INPUT" ] && exit 0

command -v jq >/dev/null 2>&1 || exit 0

AGENT=$(printf '%s' "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null)
[ "$AGENT" = "test-writer" ] || exit 0

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

# Allow: test files (mirror test-edit-telemetry.sh patterns) and fixture dirs.
case "$FILE" in
  *_test.go|*.test.ts|*.test.tsx|*.test.js|*.test.jsx|*.spec.ts|*.spec.tsx|*.spec.js|*.spec.jsx|*_spec.rb|*/test_*.py|*_test.py|*/conftest.py) exit 0 ;;
  */tests/*|*/testdata/*|*/fixtures/*|*/__tests__/*|*/__mocks__/*) exit 0 ;;
esac

# Deny only CODE files — docs/plans/config stay readable.
case "$FILE" in
  *.go|*.ts|*.tsx|*.js|*.jsx|*.py|*.rb|*.java|*.rs|*.c|*.h|*.cpp|*.hpp|*.cs|*.php|*.swift|*.kt|*.scala|*.sh) ;;
  *) exit 0 ;;
esac

REASON="test-blindness-gate: you are the test-writer and $FILE is implementation source — reading it is denied by contract, not just by prose. Your oracle is the plan; an assertion derived from the implementation codifies its accidents, which is the exact failure the coder/test-writer split exists to remove. For the public surface (signatures, types), use LSP hover/workspace-symbols or the plan's Phase 0 contracts. If the plan plus the public surface cannot specify the behavior you need to assert, that is a plan gap: report it as UNDERSPECIFIED and move on. Do not route around this via Bash (cat, git show) — that is the same read with a worse audit trail."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$REASON"
exit 0
