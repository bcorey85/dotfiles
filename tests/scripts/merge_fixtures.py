"""Git repo fixtures that leave a repo in the middle of a merge."""
import pathlib
import subprocess


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True)


def write_and_commit(repo, name, content, message):
    (pathlib.Path(repo) / name).write_text(content)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


def start_conflicted_merge(repo):
    """Leave `repo` mid-merge with a.txt resolved and staged and c.txt staged by the merge itself."""
    write_and_commit(repo, "a.txt", "base\n", "base")
    git(repo, "branch", "side")
    write_and_commit(repo, "a.txt", "ours\n", "ours")
    git(repo, "switch", "-q", "side")
    write_and_commit(repo, "a.txt", "theirs\n", "theirs")
    write_and_commit(repo, "c.txt", "new\n", "new file")
    git(repo, "switch", "-q", "-")
    merged = subprocess.run(["git", "-C", str(repo), "merge", "side"], capture_output=True, text=True)
    assert merged.returncode == 1, merged.stdout + merged.stderr
    (pathlib.Path(repo) / "a.txt").write_text("resolved\n")
    git(repo, "add", "a.txt")


def start_clean_resolved_merge(repo):
    """Leave `repo` (on branch `main`) mid-merge where both sides wrote the same b.txt, so nothing is staged."""
    write_and_commit(repo, "a.txt", "base\n", "base")
    git(repo, "branch", "side")
    write_and_commit(repo, "b.txt", "same\n", "ours")
    git(repo, "switch", "-q", "side")
    write_and_commit(repo, "b.txt", "same\n", "theirs")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "--no-commit", "--no-ff", "side")


def start_octopus_merge(repo):
    """Leave `repo` mid-merge of two branches that merge cleanly, with `--no-commit`: MERGE_HEAD
    holds two ids, and each branch adds one file. `repo` must start on branch `main` (`git init -b main`)."""
    write_and_commit(repo, "a.txt", "base\n", "base")
    for branch in ("one", "two"):
        git(repo, "switch", "-q", "-c", branch, "main")
        write_and_commit(repo, f"{branch}.txt", f"{branch}\n", f"add {branch}")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "--no-commit", "--no-ff", "one", "two")
