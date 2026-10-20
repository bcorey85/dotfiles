#!/usr/bin/env python3
"""SessionStart hook: inject ~/.claude/orchestration.md as additionalContext.

Port of emit-orchestration.sh. Main session only; subagents never see it. A readable file is emitted as
pretty-printed JSON (two-space indent, as `jq -Rs` printed it). A missing or unreadable file emits a compact
one-line warning. Always exits 0.
"""
import json
import os
import sys

MISSING_WARNING = ("WARNING: ~/.claude/orchestration.md is missing or unreadable. Delegation rules are NOT loaded "
                   "this session. Tell the user before coding or dispatching any work.")


def main():
    path = os.path.join(os.environ.get("HOME", ""), ".claude", "orchestration.md")
    if os.access(path, os.R_OK):
        try:
            with open(path, "rb") as handle:
                context = handle.read().decode("utf-8", "replace")
        except OSError:
            context = None
    else:
        context = None

    if context is not None:
        document = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
        encoded = json.dumps(document, indent=2, ensure_ascii=False)
    else:
        document = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": MISSING_WARNING}}
        encoded = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
    sys.stdout.buffer.write((encoded.replace("\x7f", "\\u007f") + "\n").encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
