"""Reads of the git index in use, for any repo: a folder of it written out as plain files, and the index file's
absolute path. A commit of named paths makes git point GIT_INDEX_FILE at a temporary index, so both honor it."""
import os
import pathlib
import subprocess


def export_index_folder(repo_dir, folder, destination):
    """Writes the files of `folder` (relative to repo_dir, which must be the repo top) as the index holds them
    under destination/<folder>/ and returns that path. A folder with no indexed file writes nothing, and the
    returned path does not exist; a git failure raises subprocess.CalledProcessError."""
    listed = subprocess.run(["git", "ls-files", "-z", "--", folder], cwd=repo_dir, capture_output=True, check=True)
    if listed.stdout:
        subprocess.run(
            ["git", "checkout-index", "-z", "--stdin", f"--prefix={destination}/"],
            cwd=repo_dir, input=listed.stdout, capture_output=True, check=True,
        )
    return pathlib.Path(destination) / folder


def index_file_path(git_dir):
    """The index in use as an absolute path: GIT_INDEX_FILE resolved against the current folder (git may set it
    relative), else <git_dir>/index."""
    named = os.environ.get("GIT_INDEX_FILE")
    if named:
        return pathlib.Path(named).resolve()
    return pathlib.Path(git_dir) / "index"
