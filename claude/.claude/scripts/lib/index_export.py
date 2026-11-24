"""A folder of the git index in use written out as plain files, for any repo. A commit of named paths makes git
point GIT_INDEX_FILE at a temporary index, which git itself honors."""
import pathlib
import subprocess


def export_index_folder(repo_dir, folder, destination):
    """Writes the files of `folder` (relative to repo_dir, which must be the repo top) as the index holds them
    under destination/<folder>/ and returns that path. A folder with no indexed file writes nothing, and the
    returned path does not exist; a git failure raises subprocess.CalledProcessError."""
    # Resolved once: git runs in repo_dir, so a relative destination would land there,
    # while the caller reads its own cwd.
    destination = pathlib.Path(destination).resolve()
    listed = subprocess.run(["git", "ls-files", "-z", "--", folder], cwd=repo_dir, capture_output=True, check=True)
    if listed.stdout:
        subprocess.run(
            ["git", "checkout-index", "-z", "--stdin", f"--prefix={destination}/"],
            cwd=repo_dir, input=listed.stdout, capture_output=True, check=True,
        )
    return destination / folder
