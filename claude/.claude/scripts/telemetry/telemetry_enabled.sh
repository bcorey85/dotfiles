#!/usr/bin/env bash
# telemetry_enabled.sh — the toolkit's metrics switch, for bash.
#
# Decided in this order:
#   1. CLAUDE_TOOLKIT_TELEMETRY=0 is off, even when the file ~/.claude/toolkit-telemetry exists.
#   2. CLAUDE_TOOLKIT_TELEMETRY=1 is on.
#   3. A session whose project folder is inside ~/dev/evals/ is off. The project folder is CLAUDE_PROJECT_DIR,
#      or the current folder when that is unset. Symlinks are resolved and whole path parts are compared, so
#      ~/dev/evals-old is not inside ~/dev/evals.
#   4. Otherwise on when the file ~/.claude/toolkit-telemetry exists, else off.
# Every metrics writer skips its write when the switch is off. The file check is temporary: it covers sessions
# started before the variable was exported, and goes away later. The check reads the environment, $HOME and the
# current folder at call time, so a test's temp HOME and env set their own switch.
#
# Run it as a command; it exits 0 when the switch is on and 1 when it is off. A writer that cannot
# run it (helper missing, not executable) counts as off:
#   "$script_dir/telemetry_enabled.sh" 2>/dev/null || exit 0
# A skill's shell line calls it the same way:
#   if "$HOME/.claude/scripts/telemetry/telemetry_enabled.sh" 2>/dev/null; then <write>; fi

# Prints the folder with symlinks resolved; a folder that does not exist prints as given.
resolve_folder() {
    (cd "$1" 2>/dev/null && pwd -P) || printf '%s\n' "$1"
}

[ "${CLAUDE_TOOLKIT_TELEMETRY:-}" = "0" ] && exit 1
[ "${CLAUDE_TOOLKIT_TELEMETRY:-}" = "1" ] && exit 0

if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    project_folder="$(resolve_folder "$CLAUDE_PROJECT_DIR")"
else
    # /bin/pwd asks the kernel, so a deleted current folder fails and counts as outside ~/dev/evals.
    project_folder="$(/bin/pwd -P 2>/dev/null)"
fi
evals_folder="$(resolve_folder "$HOME/dev/evals")"
if [ -n "$project_folder" ]; then
    case "$project_folder/" in
        "$evals_folder"/*) exit 1 ;;
    esac
fi

[ -e "$HOME/.claude/toolkit-telemetry" ]
