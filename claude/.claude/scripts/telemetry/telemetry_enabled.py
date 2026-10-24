"""The toolkit's metrics switch, for Python.

Decided by the environment alone:
  - CLAUDE_TOOLKIT_TELEMETRY=1 is on.
  - Anything else, including unset and =0, is off.
Every metrics writer skips its write when the switch is off. The check reads the environment at call time, so a
test's env sets its own switch.

Import it next to hook_input. A missing helper counts as off, so the import sits in a try block:
    try:
        from telemetry_enabled import telemetry_enabled
    except ImportError:
        def telemetry_enabled():
            return False
"""
import os


def telemetry_enabled():
    return os.environ.get("CLAUDE_TOOLKIT_TELEMETRY") == "1"
