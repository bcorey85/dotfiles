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
CODE_STEP_MODULES = ("code_step_core.py", "code_step_boundary.py", "code_step_hooks.py", "code_step_gates.py",
                     "code_step_start.py", "code_step_report.py", "code_step_review.py", "code_step_closing.py",
                     "code_step_restart.py", "code_step_start_args.py")
# A Python older than 3.14, or None: its pathlib raises on a path test of a word longer than a file name may be, where
# 3.14 returns False, so a long-text test runs the script under it.
PRE_314_PYTHON = shutil.which("python3.13") or shutil.which("python3.12") or shutil.which("python3.11")
# The sweeps that parse every real plan under ~/dev run only with REAL_PLANS=1: a stale plan in some worktree is not a
# toolkit break, so it never fails the default suite.
REAL_PLANS_ENABLED = os.environ.get("REAL_PLANS") == "1"
REAL_PLANS_SKIP_REASON = "set REAL_PLANS=1 to parse the real plans under ~/dev"


def script_in(scripts_root, name):
    """The file called `name` in whichever folder of `scripts_root` holds it."""
    found = sorted(pathlib.Path(scripts_root).glob(f"*/{name}"))
    if not found:
        raise FileNotFoundError(f"{name} is in no folder of {scripts_root}")
    return found[0]
