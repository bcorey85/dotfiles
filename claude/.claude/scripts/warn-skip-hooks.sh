#!/usr/bin/env bash
# SessionStart hook: warn when CLAUDE_SKIP_HOOKS is set.
# This is a standalone hook — not generated from YAML rules.
set -euo pipefail

if [[ -n "${CLAUDE_SKIP_HOOKS:-}" ]]; then
  printf '%s\n' '{"systemMessage":"\n⚠️⚠️⚠️\nCLAUDE_SKIP_HOOKS is set — all CB Security Hooks are bypassed for this session.\n\nTo re-enable hooks, unset the variable and restart Claude Code:\n  unset CLAUDE_SKIP_HOOKS\n⚠️⚠️⚠️"}'
fi
exit 0
