"""Where the toolkit files under test live: the installed ~/.claude, or the folder TOOLKIT_CLAUDE_DIR names."""
import os
import pathlib

CLAUDE_DIR = pathlib.Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or pathlib.Path.home() / ".claude")
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
