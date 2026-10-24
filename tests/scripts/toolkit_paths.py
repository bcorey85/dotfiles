"""Where the toolkit files under test live: the installed ~/.claude, or the folder TOOLKIT_CLAUDE_DIR names."""
import os
import pathlib

CLAUDE_DIR = pathlib.Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or pathlib.Path.home() / ".claude")
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
CODE_DIR = SCRIPTS_DIR / "code"
REVIEW_DIR = SCRIPTS_DIR / "review"
TELEMETRY_DIR = SCRIPTS_DIR / "telemetry"
LIB_DIR = SCRIPTS_DIR / "lib"
TOOLS_DIR = SCRIPTS_DIR / "tools"
GATES_DIR = SCRIPTS_DIR / "gates"


def script_in(scripts_root, name):
    """The file called `name` in whichever folder of `scripts_root` holds it."""
    found = sorted(pathlib.Path(scripts_root).glob(f"*/{name}"))
    if not found:
        raise FileNotFoundError(f"{name} is in no folder of {scripts_root}")
    return found[0]
