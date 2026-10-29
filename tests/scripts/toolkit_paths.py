"""Where the toolkit files under test live: the claude/.claude folder of the tree these tests sit in, or the folder
TOOLKIT_CLAUDE_DIR names.

Importing it also guards the real ledger: see guard_real_ledger."""
import os
import pathlib
import shutil
import tempfile

TREE_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"
CLAUDE_DIR = pathlib.Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or TREE_CLAUDE_DIR)
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
CODE_DIR = SCRIPTS_DIR / "code"
REVIEW_DIR = SCRIPTS_DIR / "review"
TELEMETRY_DIR = SCRIPTS_DIR / "telemetry"
LIB_DIR = SCRIPTS_DIR / "lib"
TOOLS_DIR = SCRIPTS_DIR / "tools"
GATES_DIR = SCRIPTS_DIR / "gates"
# Installed by the work repo's CB Security Hooks package: never tested or patched here.
WORK_HOOKS = ("scripts/bash-safety-gate.sh", "scripts/block-credential-read.sh", "scripts/write-edit-safety-gate.sh",
              "scripts/agent-model-guard.sh", "scripts/warn-skip-hooks.sh")
CODE_STEP_MODULES = ("code_step_core.py", "code_step_boundary.py", "code_step_hooks.py", "code_step_gates.py",
                     "code_step_start.py", "code_step_report.py", "code_step_review.py", "code_step_closing.py",
                     "code_step_start_args.py", "code_step_concentration.py", "code_step_phase_end.py",
                     "code_step_usage.py")
# The lib modules a copied coder_gate.py or code-step script imports.
CODE_STEP_LIB_MODULES = ("criteria_verdict.py", "shell_command.py", "makefile_text.py", "test_run_output.py",
                         "check_output.py", "check_scope.py", "numstat.py", "source_paths.py", "linked_installs.py")
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


# The env var that names the guard folder, so a reload or a child test process reuses it.
LEDGER_GUARD_VARIABLE = "TOOLKIT_TEST_LEDGER_GUARD"
# The exit code of the guard's `ledger`: EX_SOFTWARE, so a script that reaches it reports a failed ledger call.
LEDGER_GUARD_EXIT = 70
LEDGER_GUARD_SOURCE = f"""#!/bin/sh
echo "ledger: a test reached the real ledger; install fake_ledger or hide the ledger from PATH" >&2
exit {LEDGER_GUARD_EXIT}
"""


def guard_real_ledger():
    """Put a `ledger` that always fails first on PATH and point CARGO_HOME at a folder with no ledger, so a test that
    plants no stand-in can never write rows to the ledger this machine installed. A stand-in from fake_ledger.install
    goes ahead of the guard on PATH. Runs once per process tree: a child process inherits the guard."""
    guard_folder = os.environ.get(LEDGER_GUARD_VARIABLE)
    if guard_folder and os.path.isfile(os.path.join(guard_folder, "ledger")):
        return pathlib.Path(guard_folder)

    global _ledger_guard
    _ledger_guard = tempfile.TemporaryDirectory(prefix="ledger-guard-")
    guard_ledger = pathlib.Path(_ledger_guard.name) / "ledger"
    guard_ledger.write_text(LEDGER_GUARD_SOURCE)
    guard_ledger.chmod(0o755)

    os.environ[LEDGER_GUARD_VARIABLE] = _ledger_guard.name
    os.environ["PATH"] = f"{_ledger_guard.name}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["CARGO_HOME"] = _ledger_guard.name
    return pathlib.Path(_ledger_guard.name)


guard_real_ledger()
