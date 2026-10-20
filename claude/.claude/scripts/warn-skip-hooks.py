#!/usr/bin/env python3
"""SessionStart hook: warn when CLAUDE_SKIP_HOOKS is set.

Port of warn-skip-hooks.sh. Prints one line of JSON with a systemMessage when CLAUDE_SKIP_HOOKS is set to any
non-empty value, and nothing otherwise. Always exits 0.
"""
import os
import sys

MESSAGE = ('{"systemMessage":"\\n\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f\\nCLAUDE_SKIP_HOOKS is set \u2014 all CB '
           'Security Hooks are bypassed for this session.\\n\\nTo re-enable hooks, unset the variable and restart '
           'Claude Code:\\n  unset CLAUDE_SKIP_HOOKS\\n\u26a0\ufe0f\u26a0\ufe0f\u26a0\ufe0f"}\n')


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        sys.stdout.buffer.write(MESSAGE.encode("utf-8"))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
