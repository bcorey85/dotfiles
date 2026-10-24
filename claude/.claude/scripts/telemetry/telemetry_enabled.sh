#!/usr/bin/env bash
# telemetry_enabled.sh — the toolkit's metrics switch, for bash.
#
# Decided by the environment alone:
#   - CLAUDE_TOOLKIT_TELEMETRY=1 is on.
#   - Anything else, including unset and =0, is off.
# Every metrics writer skips its write when the switch is off. The check reads the environment at call time,
# so a test's env sets its own switch.
#
# Run it as a command; it exits 0 when the switch is on and 1 when it is off. A writer that cannot
# run it (helper missing, not executable) counts as off:
#   "$script_dir/telemetry_enabled.sh" 2>/dev/null || exit 0
# A skill's shell line calls it the same way:
#   if "$HOME/.claude/scripts/telemetry/telemetry_enabled.sh" 2>/dev/null; then <write>; fi

[ "${CLAUDE_TOOLKIT_TELEMETRY:-}" = "1" ]
