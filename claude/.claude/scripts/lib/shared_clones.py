"""shared_clones.py: the clones that several Claude sessions commit in at once, so their index holds peers' staged
files. The one owner of the list. CLAUDE_SHARED_CLONES (folders joined by os.pathsep) replaces the default list;
tests point it at a temp repo."""
import os
import pathlib
import subprocess
import sys

SHARED_CLONES_ENV = "CLAUDE_SHARED_CLONES"
# Two checkouts, each of which several sessions commit in. For the dotfiles entry, the main checkout only: a linked
# worktree has its own index and is another top-level folder.
DEFAULT_SHARED_CLONES = ("~/agent-evals", "~/dotfiles")
REV_PARSE_TIMEOUT_SECONDS = 10


def shared_clone_roots():
    """The resolved folders of the shared clones, `~` expanded."""
    override = os.environ.get(SHARED_CLONES_ENV)
    names = list(DEFAULT_SHARED_CLONES)
    if override is not None:
        names = [name for name in override.split(os.pathsep) if name]
    return [pathlib.Path(name).expanduser().resolve() for name in names]


def is_shared_clone(directory):
    """True when the work tree that holds `directory` is a shared clone. A folder outside any work tree is not."""
    # Fail-open on purpose: a folder git cannot answer for (no repo, a failure, a timeout) reads as not shared.
    # Not script_utils.repo_root: a failure to run git is named on stderr, not swallowed.
    command = ["git", "-C", str(directory), "rev-parse", "--show-toplevel"]
    try:
        finished = subprocess.run(command, capture_output=True, text=True, timeout=REV_PARSE_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"[shared_clones] git -C {directory} rev-parse failed ({error}); "
                         "reading the folder as not shared\n")
        return False
    top_line = finished.stdout.strip()
    if finished.returncode != 0 or not top_line:
        return False
    return pathlib.Path(top_line).resolve() in shared_clone_roots()
