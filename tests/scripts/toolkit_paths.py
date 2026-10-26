"""Where the toolkit files under test live: the claude/.claude folder of the tree these tests sit in, or the folder
TOOLKIT_CLAUDE_DIR names."""
import os
import pathlib
import shutil

TREE_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"
CLAUDE_DIR = pathlib.Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or TREE_CLAUDE_DIR)
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
CODE_DIR = SCRIPTS_DIR / "code"
REVIEW_DIR = SCRIPTS_DIR / "review"
TELEMETRY_DIR = SCRIPTS_DIR / "telemetry"
LIB_DIR = SCRIPTS_DIR / "lib"
TOOLS_DIR = SCRIPTS_DIR / "tools"
GATES_DIR = SCRIPTS_DIR / "gates"
# A Python older than 3.14, or None: its pathlib raises on a path test of a word longer than a file name may be, where
# 3.14 returns False, so a long-text test runs the script under it.
PRE_314_PYTHON = shutil.which("python3.13") or shutil.which("python3.12") or shutil.which("python3.11")


def script_in(scripts_root, name):
    """The file called `name` in whichever folder of `scripts_root` holds it."""
    found = sorted(pathlib.Path(scripts_root).glob(f"*/{name}"))
    if not found:
        raise FileNotFoundError(f"{name} is in no folder of {scripts_root}")
    return found[0]
