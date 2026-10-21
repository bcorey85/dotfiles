#!/usr/bin/env bash
# telemetry_enabled.sh — the toolkit's metrics switch, for bash.
#
# On when CLAUDE_TOOLKIT_TELEMETRY=1 is set, or when the file ~/.claude/toolkit-telemetry exists.
# Otherwise every metrics writer skips its write. The file check is temporary: it covers sessions
# started before the variable was exported, and goes away later. The check reads the environment and
# $HOME at call time, so a test's temp HOME and env set their own switch.
#
# Run it as a command; it exits 0 when the switch is on and 1 when it is off. A writer that cannot
# run it (helper missing, not executable) counts as off:
#   "$script_dir/telemetry_enabled.sh" 2>/dev/null || exit 0
# A skill's shell line calls it the same way:
#   if "$HOME/.claude/scripts/telemetry_enabled.sh" 2>/dev/null; then <write>; fi

[ "${CLAUDE_TOOLKIT_TELEMETRY:-}" = "1" ] || [ -e "$HOME/.claude/toolkit-telemetry" ]
