"""Limits the Claude Code harness enforces on a tool call. No imports: the gates load this module on every Bash call."""

# The harness moves a Bash call that runs past this many seconds to the background.
BACKGROUND_AFTER_SECONDS = 180
