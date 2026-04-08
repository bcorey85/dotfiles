#!/usr/bin/env bash
# SessionStart hook: warn when CLAUDE_SKIP_HOOKS is set.
# This is a standalone hook — not generated from YAML rules.
set -euo pipefail

if [[ -n "${CLAUDE_SKIP_HOOKS:-}" ]]; then
  cat <<'EOF'
⚠️  CLAUDE_SKIP_HOOKS is set — all security hooks from agentic-engineering-standards are bypassed for this session.

To re-enable hooks, unset the variable and restart Claude Code:
  unset CLAUDE_SKIP_HOOKS
EOF
fi
exit 0
