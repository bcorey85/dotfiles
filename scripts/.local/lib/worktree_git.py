"""Git runner and worktree list shared by herdr-worktree-prune and its branch module."""
from __future__ import annotations

import dataclasses
import os
import subprocess

from quiet_git import run_quiet_git

HEADS_PREFIX = "refs/heads/"


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

    def merge_targets(self):
        """Every (name, hash) a lane's tip may be merged into: the compare ref, then the main checkout's branch
        when it has one whose commit differs from the compare hash."""
        targets = [(self.compare_name, self.compare_hash)]
        if self.checkout_name is not None and self.checkout_hash != self.compare_hash:
            targets.append((self.checkout_name, self.checkout_hash))
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


def checkout_tip(repo):
    """The commit of the main checkout's branch now, or None when it cannot be read."""
    resolved = git(repo.main_path, "rev-parse", "--verify", "--quiet", f"{HEADS_PREFIX}{repo.checkout_name}^{{commit}}")
    if resolved.returncode != 0:
        return None
    return resolved.stdout.strip()


def merged_into(repo, commit):
    """Whether `commit` is an ancestor of the compare ref or of the main checkout's branch.

    The checkout branch is asked by its live ref, not by the hash taken at start-up: the branch can move during a
    run. A commit equal to the checkout branch's tip does not count as merged into it: a fresh worktree cut from
    that branch, or a branch it was just made from, holds no work of its own."""
    for index, (name, target_hash) in enumerate(repo.merge_targets()):
        is_checkout = index > 0
        target = f"{HEADS_PREFIX}{name}" if is_checkout else target_hash
        asked = git(repo.main_path, "merge-base", "--is-ancestor", commit, target)
        if asked.returncode == 1:
            continue
        if asked.returncode != 0:
            return MergeVerdict(error=f"git merge-base failed: {asked.stderr.strip()}")
        if is_checkout and commit == checkout_tip(repo):
            continue
        return MergeVerdict(target=name)
    return MergeVerdict()


def not_on_text(repo):
    """'origin/main' or 'origin/main nor on bench-base': the refs a commit is missing from."""
    names = [name for name, _ in repo.merge_targets()]
    return " nor on ".join(names)
