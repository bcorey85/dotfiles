#!/usr/bin/env python3
"""SessionStart hook: inject ~/.claude/orchestration.md as additionalContext.

Main session only; emits nothing when the hook input has `agent_type` (an `--agent` seat), since the rules
tell it not to code. A readable file is emitted as pretty-printed JSON (two-space indent, as `jq -Rs`
printed it). A missing or unreadable file emits a compact one-line warning. Always exits 0.
"""
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
import hook_input

MISSING_WARNING = ("WARNING: ~/.claude/orchestration.md is missing or unreadable. Delegation rules are NOT loaded "
                   "this session. Tell the user before coding or dispatching any work.")


def is_agent_seat():
    """True when the hook input is a JSON object with a non-empty string agent_type."""
    try:
        event_text = hook_input.read_stdin_text()
    except OSError as error:
        # Fail closed: unreadable input is treated as a main session, so the rules load.
        hook_input.emit_stderr(f"{hook_input.hook_name()}: cannot read hook input ({error}); loading rules\n")
        return False
    if not event_text:
        return False

    try:
        event = json.loads(event_text)
    except ValueError as error:
        # Fail closed: unparseable input is treated as a main session, so the rules load.
        hook_input.emit_stderr(f"{hook_input.hook_name()}: cannot parse hook input ({error}); loading rules\n")
        return False
    if not isinstance(event, dict):
        return False
    agent_type = event.get("agent_type")
    return isinstance(agent_type, str) and agent_type != ""


def main():
    if is_agent_seat():
        return 0

    path = os.path.join(os.environ.get("HOME", ""), ".claude", "orchestration.md")
    context = hook_input.read_file_text(path, errors="replace")

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
