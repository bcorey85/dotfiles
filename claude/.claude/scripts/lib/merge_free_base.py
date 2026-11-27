"""merge_free_base.py: a base commit for a review diff that leaves out what merge commits brought in.

`merge_free_base(repo, base)` returns `base` itself when `base..HEAD` holds no merge commit. Otherwise it folds each
merged-in parent into the base, oldest merge first: the tree of `git merge-tree --write-tree <base> <parent>` is made a
commit object with `git commit-tree` (no ref, so nothing in the repo points at it). `git diff <that commit>` then shows
the branch's own change and not the merged-in branch's. Only first-parent merges are listed: a merged-in tip already
holds what the merges inside its own branch brought.

`resolve_base(repo, base, name)` replaces a base that is no ancestor of HEAD with its merge base with HEAD, and
returns a `BaseResolution` that says whether the base moved.
"""
import subprocess
from typing import NamedTuple

GIT_USER = ("-c", "user.name=review", "-c", "user.email=review@localhost")
MERGE_TREE_CONFLICT_EXIT = 1
GIT_VERSION_NEED = "`git merge-tree --write-tree` needs git 2.38 or later"


class MergeConflictError(Exception):
    """A merged-in parent that does not merge cleanly into the base; `merge` is the merge commit that holds it."""

    def __init__(self, merge, parent, detail):
        super().__init__(f"merge commit {merge} (its merged-in parent {parent}) does not merge cleanly into the "
                         f"review base: {detail}")
        self.merge = merge


class MergeBaseGitError(Exception):
    """A git call that failed for a reason other than a merge conflict."""


class NoMergeBaseError(Exception):
    """A base that shares no history with HEAD, so no merge base exists. The message names the recovery command."""


class BaseResolution(NamedTuple):
    """`given` is the base as the caller named it, `commit` the commit that name resolved to, and `used` the commit
    the review diffs against."""
    given: str
    commit: str
    used: str

    def given_if_moved(self):
        """`given` when `used` is not the commit that `given` named, else None."""
        if self.used == self.commit:
            return None
        return self.given


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def resolve_base(repo, base, name=None):
    """BaseResolution(given, commit, used): `commit` is `base`; `used` is `base` when it is an ancestor of HEAD, else
    `git merge-base HEAD base`, so a base ref whose tip moved ahead does not show its own unmerged commits as
    reverts. Raises NoMergeBaseError when HEAD and `base` share no history, and MergeBaseGitError when git fails.
    `name` is the base as given (`given`, and how the error calls it), `base` when None."""
    name = name or base
    ancestor = _git(repo, "merge-base", "--is-ancestor", base, "HEAD")
    if ancestor.returncode == 0:
        return BaseResolution(name, base, base)
    if ancestor.returncode != 1:
        raise MergeBaseGitError(f"git merge-base --is-ancestor {base} HEAD failed: {ancestor.stderr.strip()}")

    found = _git(repo, "merge-base", "HEAD", base)
    if found.returncode == 1:
        raise NoMergeBaseError(f"HEAD and the review base {name} have no merge base, so no diff against it holds only "
                               f"the branch's own change. Run `git merge-base HEAD {name}` to confirm, then pass a "
                               "--base that shares history with HEAD (fetch it first when it is a remote ref).")
    if found.returncode != 0:
        raise MergeBaseGitError(f"git merge-base HEAD {base} failed: {found.stderr.strip()}")
    return BaseResolution(name, base, found.stdout.strip())


def merge_commits(repo, base):
    """The first-parent merge commits of base..HEAD, oldest first. Raises MergeBaseGitError when git cannot list
    them."""
    listed = _git(repo, "rev-list", "--merges", "--first-parent", "--reverse", f"{base}..HEAD")
    if listed.returncode != 0:
        raise MergeBaseGitError(f"git rev-list --merges {base}..HEAD failed: {listed.stderr.strip()}")
    return listed.stdout.split()


def merged_in_parents(repo, merge):
    """The parents of `merge` after its first. Raises MergeBaseGitError when git cannot list them."""
    listed = _git(repo, "rev-list", "--parents", "-n", "1", merge)
    if listed.returncode != 0:
        raise MergeBaseGitError(f"git rev-list --parents {merge} failed: {listed.stderr.strip()}")
    return listed.stdout.split()[2:]


def conflicted_paths(merge_tree_output):
    """The paths `git merge-tree --name-only` lists after the tree id, up to its first blank line."""
    lines = merge_tree_output.splitlines()[1:]
    paths = []
    for line in lines:
        if not line.strip():
            break
        paths.append(line.strip())
    return paths


def fold_parent(repo, merge, current, parent):
    """The commit that folds `parent` into `current`. Raises MergeConflictError when the parent conflicts, and
    MergeBaseGitError when git fails otherwise."""
    merged = _git(repo, "merge-tree", "--write-tree", "--name-only", "--allow-unrelated-histories", current,
                  parent)
    if merged.returncode == MERGE_TREE_CONFLICT_EXIT:
        paths = conflicted_paths(merged.stdout)
        detail = merged.stderr.strip()
        if paths:
            detail = "conflicts in " + ", ".join(paths)
        raise MergeConflictError(merge, parent, detail)
    if merged.returncode != 0:
        raise MergeBaseGitError(f"git merge-tree of {current} and {parent} failed (exit {merged.returncode}): "
                                f"{merged.stderr.strip()}. {GIT_VERSION_NEED}.")

    tree = merged.stdout.split()[0]
    made = _git(repo, *GIT_USER, "commit-tree", "--no-gpg-sign", tree, "-p", current, "-m",
                f"review base: {parent} folded in")
    if made.returncode != 0:
        raise MergeBaseGitError(f"git commit-tree for {tree} failed: {made.stderr.strip()}")
    return made.stdout.strip()


def merge_free_base(repo, base):
    """`base`, or a commit object whose tree has every merged-in parent of base..HEAD folded into `base`. Raises
    MergeConflictError, naming the merge, when a parent conflicts, and MergeBaseGitError when git fails."""
    current = base
    for merge in merge_commits(repo, base):
        for parent in merged_in_parents(repo, merge):
            current = fold_parent(repo, merge, current, parent)
    return current
