"""Executable stand-ins for the commands a script under test calls."""
import pathlib
import shutil

TOOLKIT_TOOLS_LIB = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "lib" / "toolkit-tools.bash"


def copy_toolkit_tools_lib(root):
    """Copy the library a script sources to <root>/lib, where a copy of the script in <root>/bin finds it."""
    lib_dir = pathlib.Path(root) / "lib"
    lib_dir.mkdir(exist_ok=True)
    shutil.copy(TOOLKIT_TOOLS_LIB, lib_dir / TOOLKIT_TOOLS_LIB.name)


def write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)
