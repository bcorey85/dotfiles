"""Stand-ins for the commands a script under test calls, and helpers that lay out and run a copy of the script."""
import pathlib
import shutil
import subprocess

SCRIPT_LIB_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "lib"
SOURCED_LIBS = ("toolkit-tools.bash", "main-checkout.bash", "branch-claim.bash")


def copy_sourced_libs(root):
    """Copy the libraries a script sources to <root>/lib, where a copy of the script in <root>/bin finds them."""
    lib_dir = pathlib.Path(root) / "lib"
    lib_dir.mkdir(exist_ok=True)
    for lib_name in SOURCED_LIBS:
        shutil.copy(SCRIPT_LIB_DIR / lib_name, lib_dir / lib_name)


def write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)


def run_through_stow_symlink(script, scratch, *args):
    """Run a copy of `script` through a symlink in a bin folder whose parent has no lib.

    The real script and the library sit in a separate checkout, as stow links them.
    """
    scratch = pathlib.Path(scratch)
    real_bin = scratch / "checkout" / "scripts" / ".local" / "bin"
    real_bin.mkdir(parents=True)
    real_script = real_bin / script.name
    shutil.copy(script, real_script)
    copy_sourced_libs(real_bin.parent)
    linked_bin = scratch / "linked" / "bin"
    linked_bin.mkdir(parents=True)
    (linked_bin / script.name).symlink_to(real_script)
    return subprocess.run([str(linked_bin / script.name), *args], capture_output=True, text=True, timeout=30)
