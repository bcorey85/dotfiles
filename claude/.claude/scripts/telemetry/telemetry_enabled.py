"""The toolkit's metrics switch, for Python.

Decided by the environment alone:
  - CLAUDE_TOOLKIT_TELEMETRY=1 is on.
  - Anything else, including unset and =0, is off.
Every metrics writer skips its write when the switch is off. The check reads the environment at call time, so a
test's env sets its own switch.

Python callers ask script_utils.telemetry_switch_on(), which counts a missing helper as off.
"""
import os


def telemetry_enabled():
    return os.environ.get("CLAUDE_TOOLKIT_TELEMETRY") == "1"
