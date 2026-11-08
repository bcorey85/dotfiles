"""Usage: pull_keep_index.py <repo>

Run `git pull --rebase=merges` in the repo with its local changes set aside and put back after, staged files still
staged. `--autostash` puts them back unstaged. The changes are saved as a dangling stash commit, never on the shared
stash stack. Exit 0 when the pull ran and the changes are back; exit 1 with the recovery command otherwise."""
import os
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import script_utils


def recovery_text(repo, saved):
    return f"The local changes are saved in {saved}; on a clean tree, run: git -C {repo} stash apply --index {saved}"


def rebase_in_progress(repo):
    for name in ("rebase-merge", "rebase-apply"):
        found = script_utils.git_output(repo, "rev-parse", "--git-path", name)
        if found and os.path.exists(os.path.join(repo, found)):
            return True
    return False


def set_aside(repo):
    """Save the local changes as a stash commit and reset to HEAD; the commit id, or "" for a clean tree."""
    saved = script_utils.git_output(repo, "stash", "create")
    if saved is None:
        sys.exit(f"pull_keep_index: git stash create failed in {repo}")
    if not saved:
        return saved

    reset = subprocess.run(["git", "-C", repo, "reset", "--hard", "--quiet"], capture_output=True, text=True)
    if reset.returncode != 0:
        sys.exit(f"pull_keep_index: git reset failed: {reset.stderr.strip()}. " + recovery_text(repo, saved))
    return saved


def put_back(repo, saved):
    """Apply the saved changes with their index; exit 1 naming the recovery command when that fails."""
    applied = subprocess.run(["git", "-C", repo, "stash", "apply", "--index", "--quiet", saved],
                             capture_output=True, text=True)
    if applied.returncode == 0:
        return
    sys.stderr.write(applied.stderr)
    sys.exit("pull_keep_index: the local changes did not go back on cleanly. " + recovery_text(repo, saved))


def main(arguments):
    if len(arguments) != 1:
        sys.exit(__doc__)
    repo = arguments[0]

    saved = set_aside(repo)
    pulled = subprocess.run(["git", "-C", repo, "pull", "--rebase=merges", "--no-autostash"])
    if pulled.returncode != 0 and rebase_in_progress(repo):
        recovery = " " + recovery_text(repo, saved) if saved else ""
        sys.exit("pull_keep_index: the pull stopped mid-rebase." + recovery)

    if saved:
        put_back(repo, saved)
    if pulled.returncode != 0:
        sys.exit(f"pull_keep_index: git pull failed in {repo}; the local changes are back in place.")


if __name__ == "__main__":
    main(sys.argv[1:])
