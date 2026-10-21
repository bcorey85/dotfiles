"""The toolkit's metrics switch, for Python.

On when CLAUDE_TOOLKIT_TELEMETRY=1 is set, or when the file ~/.claude/toolkit-telemetry exists. Otherwise every
metrics writer skips its write. The file check is temporary: it covers sessions started before the variable was
exported, and goes away later. The check reads the environment and HOME at call time, so a test's temp HOME and env
set their own switch.

Import it next to hook_input. A missing helper counts as off, so the import sits in a try block:
    try:
        from telemetry_enabled import telemetry_enabled
    except ImportError:
        def telemetry_enabled():
            return False
"""
import os


def telemetry_enabled():
    if os.environ.get("CLAUDE_TOOLKIT_TELEMETRY") == "1":
        return True
    home = os.path.expanduser("~")
    return os.path.exists(os.path.join(home, ".claude", "toolkit-telemetry"))
