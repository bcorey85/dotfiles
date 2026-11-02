"""A repo's quality check named in the machine-local `CLAUDE.local.md`, never in the repo.

One entry per line: ``Quality check (<repo name>): `<command>` ``, as a bare line or a list item. The repo name is the
folder name of the repo's main checkout, found through the git common dir, so a linked worktree with another folder
name matches the same entry. HOME comes from the environment."""
import os
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent)]

import script_utils

LOCAL_FILE = pathlib.Path(".claude") / "CLAUDE.local.md"
# group 1 is the repo name, group 2 the command.
LOCAL_CHECK_LINE = re.compile(r"^\s*[-*]?\s*Quality check \(([^)]+)\):\s*`([^`]+)`", re.I | re.M)


def main_checkout_name(repo):
    """The folder name of the main checkout of the repo that holds `repo`: that of a linked worktree's main checkout
    too. Outside git, or with a git that cannot answer, the folder name of `repo` itself."""
    repo_path = pathlib.Path(repo).resolve()
    common_dir = script_utils.git_output(repo_path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common_dir:
        return repo_path.name

    common_path = pathlib.Path(common_dir)
    if common_path.name == ".git":
        return common_path.parent.name
    return common_path.name.removesuffix(".git")


def local_check_command(repo):
    """The command of the repo's entry in the home folder's CLAUDE.local.md, or None when the file or the entry is
    missing."""
    home = pathlib.Path(os.environ.get("HOME") or pathlib.Path.home())
    local_file = home / LOCAL_FILE
    if not local_file.is_file():
        return None

    repo_name = main_checkout_name(repo)
    for match in LOCAL_CHECK_LINE.finditer(local_file.read_text(errors="replace")):
        if match.group(1).strip() == repo_name:
            return match.group(2)
    return None
