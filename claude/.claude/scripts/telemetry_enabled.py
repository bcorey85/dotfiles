"""The toolkit's metrics switch, for Python.

Decided in this order:
  1. CLAUDE_TOOLKIT_TELEMETRY=0 is off, even when the file ~/.claude/toolkit-telemetry exists.
  2. CLAUDE_TOOLKIT_TELEMETRY=1 is on.
  3. A session whose project folder is inside ~/dev/evals/ is off. The project folder is CLAUDE_PROJECT_DIR, or the
     current folder when that is unset. Symlinks are resolved and whole path parts are compared, so ~/dev/evals-old
     is not inside ~/dev/evals.
  4. Otherwise on when the file ~/.claude/toolkit-telemetry exists, else off.
Every metrics writer skips its write when the switch is off. The file check is temporary: it covers sessions started
before the variable was exported, and goes away later. The check reads the environment, HOME and the current folder at
call time, so a test's temp HOME and env set their own switch.

Import it next to hook_input. A missing helper counts as off, so the import sits in a try block:
    try:
        from telemetry_enabled import telemetry_enabled
    except ImportError:
        def telemetry_enabled():
            return False
"""
import os


def resolve_folder(folder):
    # A folder that does not exist stays as given, the same as telemetry_enabled.sh.
    if os.path.isdir(folder):
        return os.path.realpath(folder)
    return folder


def inside_evals_folder(home):
    try:
        projectFolder = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        resolvedProject = resolve_folder(projectFolder)
        evalsFolder = resolve_folder(os.path.join(home, "dev", "evals"))
    except OSError:
        return False

    # Compare the way telemetry_enabled.sh does: the project folder plus a slash starts with the evals folder plus
    # a slash, so whole path parts match and ~/dev/evals-old does not.
    return (resolvedProject + "/").startswith(evalsFolder + "/")


def telemetry_enabled():
    setting = os.environ.get("CLAUDE_TOOLKIT_TELEMETRY")
    if setting == "0":
        return False
    if setting == "1":
        return True

    home = os.path.expanduser("~")
    if inside_evals_folder(home):
        return False

    return os.path.exists(os.path.join(home, ".claude", "toolkit-telemetry"))
