"""Where the toolkit files under test live: the claude/.claude folder of the tree these tests sit in, or the folder
TOOLKIT_CLAUDE_DIR names.

Importing it also guards the real ledger: see guard_real_ledger."""
import os
import pathlib
import shutil
import subprocess
import tempfile

TREE_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude"
CLAUDE_DIR = pathlib.Path(os.environ.get("TOOLKIT_CLAUDE_DIR") or TREE_CLAUDE_DIR)
REPO_ROOT = TREE_CLAUDE_DIR.parents[1]
OPENCODE_AGENTS_DIR = REPO_ROOT / "opencode" / ".config" / "opencode" / "agents"
RIPGREP_CONFIG = REPO_ROOT / "ripgrep" / ".config" / "ripgrep" / "config"
ZSHENV_DIR = REPO_ROOT / "zsh"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
CODE_DIR = SCRIPTS_DIR / "code"
REVIEW_DIR = SCRIPTS_DIR / "review"
TELEMETRY_DIR = SCRIPTS_DIR / "telemetry"
LIB_DIR = SCRIPTS_DIR / "lib"
TOOLS_DIR = SCRIPTS_DIR / "tools"
GATES_DIR = SCRIPTS_DIR / "gates"
FIX_DIFF_SCRIPT = pathlib.Path(os.environ.get("FIX_DIFF_PATH")
                               or CLAUDE_DIR / "skills" / "close-branch" / "scripts" / "fix_diff.py")
CODE_SKILL_FILE = CLAUDE_DIR / "skills" / "code" / "SKILL.md"
CODE_PHASE_END_FILE = CLAUDE_DIR / "skills" / "code" / "phase-end-block.md"
CODE_FORK_AGENT_FILE = CLAUDE_DIR / "agents" / "code-fork.md"
# The hooks come from the work repo's CB Security Hooks package and are not tested here, except
# agent-model-guard.sh: it carries a local fork pass, tested in test_agent_model_guard.py,
# that the package must carry too.
WORK_HOOKS = ("scripts/bash-safety-gate.sh", "scripts/block-credential-read.sh", "scripts/write-edit-safety-gate.sh",
              "scripts/agent-model-guard.sh", "scripts/warn-skip-hooks.sh")
# The lib modules a copied coder_gate.py imports.
CODER_GATE_LIB_MODULES = ("criteria_verdict.py", "shell_command.py", "shell_directory.py", "shell_quoting.py",
                          "makefile_text.py",
                          "test_run_output.py", "check_output.py", "check_scope.py", "numstat.py", "source_paths.py",
                          "linked_installs.py", "worktree_snapshot.py", "expected_red.py", "full_check_receipt.py",
                          "reviewed_tree.py", "pytest_config.py", "notes_paths.py", "ansi_text.py", "code_text.py",
                          "gate_env.py", "plan_format.py", "source_text.py", "collision_retry.py",
                          "ask_outcome_words.py", "import_guard.py")


def first_python_that_starts(names):
    """The real path of the first named Python that starts, or None.

    A version manager leaves a shim on PATH for a Python it no longer runs, and a shim that runs here can still fail
    under a test's own HOME. So each one found is started, and the path it reports for itself is the one returned."""
    for name in names:
        found = shutil.which(name)
        if not found:
            continue
        started = subprocess.run([found, "-c", "import sys; print(sys.executable)"],
                                 capture_output=True, text=True, check=False)
        if started.returncode != 0:
            continue
        return started.stdout.strip()
    return None


# A Python older than 3.14, or None: its pathlib raises on a path test of a word longer than a file name may be, where
# 3.14 returns False, so a long-text test runs the script under it.
PRE_314_PYTHON = first_python_that_starts(("python3.13", "python3.12", "python3.11"))
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


def absolutize_import_paths():
    """Make each relative entry of PYTHONPATH and NODE_PATH absolute against the current folder. A test that runs a
    check in a nested fixture repo would otherwise read `tests/scripts` as a path inside that repo."""
    for variable in ("PYTHONPATH", "NODE_PATH"):
        entries = os.environ.get(variable)
        if not entries:
            continue
        os.environ[variable] = os.pathsep.join(
            os.path.abspath(entry) if entry else entry for entry in entries.split(os.pathsep))


guard_real_ledger()
absolutize_import_paths()
