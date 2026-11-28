"""Git runner and worktree list shared by herdr-worktree-prune and its branch module."""
from __future__ import annotations

import dataclasses
import os
import subprocess

from quiet_git import run_quiet_git

HEADS_PREFIX = "refs/heads/"
UNBORN_HEAD = "0" * 40  # what `git worktree list` prints as HEAD for a branch with no commit


class PruneError(Exception):
    """A failure to read git state. Before the first removal it stops the run with nothing removed and exit 1.
    Mid-apply it fails only the tree or branch being handled: the run goes on, prints its totals and exits 1."""


@dataclasses.dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str


@dataclasses.dataclass
class Worktree:
    path: str
    head: str = ""
    branch: str | None = None
    bare: bool = False
    detached: bool = False
    locked: bool = False
    lock_reason: str = ""
    prunable: bool = False


@dataclasses.dataclass
class Repo:
    main_path: str
    default_branch: str
    compare_name: str
    compare_hash: str
    cwd_real: str
    # The branch the main checkout has checked out and its commit; None when main is detached or bare.
    checkout_name: str | None = None
    checkout_hash: str | None = None

    def merge_targets(self, except_name=None, linked=()):
        """Every (name, hash) a lane's tip may be merged into: the compare ref, the main checkout's branch when it
        has one whose commit differs from the compare hash, then the branch of every worktree in `linked` that is
        not prunable, detached or unborn and whose commit differs from the compare hash.
        `linked` holds the linked worktrees allowed to give credit (none by default); the caller leaves out the
        trees of open lanes. The branch `except_name` is left out: it is the one being judged, which holds no
        merge of itself."""
        targets = [(self.compare_name, self.compare_hash)]
        if self.checkout_name is not None and self.checkout_hash != self.compare_hash:
            targets.append((self.checkout_name, self.checkout_hash))
        named = {name for name, _ in targets}
        named.add(except_name)
        for tree in linked:
            if tree.bare or tree.prunable or tree.detached or tree.branch is None or tree.head == UNBORN_HEAD:
                continue
            if tree.branch in named or tree.head == self.compare_hash:
                continue
            named.add(tree.branch)
            targets.append((tree.branch, tree.head))
        return targets


@dataclasses.dataclass
class Tally:
    removed: int = 0
    freed: int = 0
    kept: int = 0
    failed: int = 0


def run(args, cwd=None, timeout=None, env=None):
    try:
        done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                              errors="surrogateescape", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return Result(127, "", f"{args[0]}: {error}")
    return Result(done.returncode, done.stdout, done.stderr)


def git(directory, *args, timeout=None):
    """Run git in `directory` (the working directory when None) without prompts or optional index writes."""
    try:
        done = run_quiet_git(directory, *args, timeout=timeout, errors="surrogateescape")
    except (OSError, subprocess.TimeoutExpired) as error:
        return Result(127, "", f"git: {error}")
    return Result(done.returncode, done.stdout, done.stderr)


def real(path):
    return os.path.realpath(path)


def inside(child, parent):
    """True when `child` is `parent` or lies below it, compared on whole path components."""
    if child == parent:
        return True
    return child.startswith(parent.rstrip(os.sep) + os.sep)


def show(path):
    """The path with control characters escaped, so one path stays one line."""
    return "".join(char if char.isprintable() else char.encode("unicode_escape").decode("ascii")
                   for char in path)


# ---- git worktree list ----

def worktree_from_fields(fields):
    first = fields[0]
    if not first.startswith("worktree "):
        raise PruneError(f"git worktree list: expected a `worktree <path>` field, got {first!r}")
    tree = Worktree(path=first[len("worktree "):])
    for field in fields[1:]:
        apply_worktree_field(tree, field)
    return tree


def apply_worktree_field(tree, field):
    key, _, value = field.partition(" ")
    if key == "HEAD":
        tree.head = value
    elif key == "branch":
        tree.branch = value[len(HEADS_PREFIX):] if value.startswith(HEADS_PREFIX) else value
    elif key == "bare":
        tree.bare = True
    elif key == "detached":
        tree.detached = True
    elif key == "locked":
        tree.locked = True
        tree.lock_reason = value
    elif key == "prunable":
        tree.prunable = True
    else:
        raise PruneError(f"git worktree list: unknown field {field!r}; expected HEAD, branch, bare, "
                         "detached, locked or prunable")


def parse_worktrees(listing):
    """Read `git worktree list --porcelain -z`: NUL-ended fields, an empty field between entries."""
    worktrees = []
    for block in listing.split("\0\0"):
        fields = [field for field in block.split("\0") if field]
        if fields:
            worktrees.append(worktree_from_fields(fields))
    if not worktrees:
        raise PruneError("git worktree list printed no entries")
    return worktrees


def list_worktrees(main_dir):
    listing = git(main_dir, "worktree", "list", "--porcelain", "-z")
    if listing.returncode != 0:
        raise PruneError(f"git worktree list failed: {listing.stderr.strip()}")
    return parse_worktrees(listing.stdout)


@dataclasses.dataclass
class MergeVerdict:
    """`target` names the ref that holds the commit; `error` is a git failure; both None means held by none."""
    target: str | None = None
    error: str | None = None


def branch_tip(repo, name):
    """The commit hash of refs/heads/<name> now, or None."""
    resolved = git(repo.main_path, "rev-parse", "--verify", "--quiet", f"{HEADS_PREFIX}{name}^{{commit}}")
    if resolved.returncode != 0:
        return None
    return resolved.stdout.strip()


def merged_into(repo, commit, linked=(), own_branch=None):
    """Whether `commit` is an ancestor of the compare ref, of the main checkout's branch or of the branch of any
    linked worktree that is not prunable, detached or unborn and is in `linked`, leaving out `own_branch`, the
    branch being judged.

    Those branches are asked by their live refs, not by the hash taken at start-up: a branch can move during a
    run. A commit equal to such a branch's tip does not count as merged into it: a fresh worktree cut from
    that branch, or a branch it was just made from, holds no work of its own."""
    targets = repo.merge_targets(except_name=own_branch, linked=linked)
    compare_name, compare_hash = targets[0]
    asked = git(repo.main_path, "merge-base", "--is-ancestor", commit, compare_hash)
    if asked.returncode == 0:
        return MergeVerdict(target=compare_name)
    if asked.returncode != 1:
        return MergeVerdict(error=f"git merge-base failed: {asked.stderr.strip()}")
    branch_names = [name for name, _ in targets[1:]]
    if not branch_names:
        return MergeVerdict()
    branch_refs = [f"{HEADS_PREFIX}{name}" for name in branch_names]
    containing = git(repo.main_path, "for-each-ref", f"--contains={commit}",
                     "--format=%(refname:strip=2) %(objectname)", *branch_refs)
    if containing.returncode != 0:
        return MergeVerdict(error=f"git for-each-ref failed: {containing.stderr.strip()}")
    holders = set()
    for row in containing.stdout.splitlines():
        name, _, tip = row.rpartition(" ")
        if tip != commit:
            holders.add(name)
    for name in branch_names:
        if name in holders:
            return MergeVerdict(target=name)
    return MergeVerdict()


def not_on_text(repo, own_branch=None, linked=()):
    """'origin/main' or 'origin/main nor on bench-base': the refs the branch `own_branch` is missing from."""
    names = [name for name, _ in repo.merge_targets(except_name=own_branch, linked=linked)]
    return " nor on ".join(names)
