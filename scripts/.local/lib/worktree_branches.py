"""Branch deletion and branch mode of herdr-worktree-prune."""
from __future__ import annotations

import dataclasses
import os
import pathlib

from worktree_git import (
    HEADS_PREFIX,
    PruneError,
    Tally,
    branch_tip,
    git,
    list_worktrees,
    merged_into,
    not_on_text,
    show,
)

# ---- branch deletion (both modes) ----

# `git config --remove-section` exits 128 and prints this when the section is not there.
NO_SUCH_SECTION_EXIT = 128
NO_SUCH_SECTION_TEXT = "no such section"


@dataclasses.dataclass
class BranchDeletion:
    failure: str | None = None  # why the branch stays; None when it is deleted
    warning: str | None = None  # a problem after a successful delete


def ahead_text(repo, name):
    """Two spaces and a note when the branch has an upstream whose tip does not hold the branch tip, else ''."""
    tip = branch_tip(repo, name)
    named = git(repo.main_path, "for-each-ref", "--format=%(upstream)", f"{HEADS_PREFIX}{name}")
    upstream_ref = named.stdout.strip()
    if tip is None or named.returncode != 0 or not upstream_ref:
        return ""
    upstream = git(repo.main_path, "rev-parse", "--verify", "--quiet", f"{upstream_ref}^{{commit}}")
    if upstream.returncode != 0:
        return ""
    held = git(repo.main_path, "merge-base", "--is-ancestor", tip, upstream.stdout.strip())
    if held.returncode != 1:
        return ""
    verdict = merged_into(repo, tip)
    if verdict.target is None:
        return ""
    return f"  ahead of its own remote branch, fully on {verdict.target}"


def remove_branch_config(repo, name):
    """A warning when the `branch.<name>` section could not be removed, else None. A missing section is fine."""
    removed = git(repo.main_path, "config", "--remove-section", f"branch.{name}")
    if removed.returncode == 0:
        return None
    if removed.returncode == NO_SUCH_SECTION_EXIT and NO_SUCH_SECTION_TEXT in removed.stderr:
        return None
    return (f"warning: branch {name} is deleted but its config section stays: git config --remove-section "
            f"branch.{name} failed: {removed.stderr.strip() or removed.returncode}")


def delete_branch(repo, name):
    """Delete refs/heads/<name> with `git update-ref -d` on the tip just proven an ancestor of the compare hash
    or of the main checkout's branch.

    Git refuses the delete when the tip moved after the check. Never `branch -D`, never a delete without the old
    value. Only that one ref is named, so `fix/a` never touches `fix/a-b`."""
    tip = branch_tip(repo, name)
    if tip is None:
        return BranchDeletion(failure="the branch ref cannot be read (already gone?)")
    verdict = merged_into(repo, tip)
    if verdict.error is not None:
        return BranchDeletion(failure=verdict.error)
    if verdict.target is None:
        return BranchDeletion(failure=f"its tip {tip[:8]} is not on {not_on_text(repo)}")
    deleted = git(repo.main_path, "update-ref", "-d", f"{HEADS_PREFIX}{name}", tip)
    if deleted.returncode != 0:
        return BranchDeletion(failure="git update-ref -d refused (the tip moved or the ref is locked): "
                                      f"{deleted.stderr.strip()}")
    return BranchDeletion(warning=remove_branch_config(repo, name))


# ---- branch mode ----

CHECKED_OUT_REASON = "a worktree has it checked out now"
# Files in a worktree's git dir that name the branch a rebase or bisect started on.
REBASE_HEAD_NAME_FILES = (("rebase-merge", "head-name"), ("rebase-apply", "head-name"))
BISECT_START_FILE = "BISECT_START"


def read_git_dir_file(git_dir, parts):
    """The first line of a file in the git dir, or None when the file is absent. An unreadable file stops the run:
    without it a branch in use could be deleted."""
    file = git_dir.joinpath(*parts)
    if not file.is_file():
        return None
    try:
        text = file.read_text()
    except OSError as error:
        raise PruneError(f"cannot read {file}: {error}") from error
    return text.strip()


def branches_in_progress(tree_path):
    """The branches a rebase or bisect in this worktree started on.

    Such a worktree shows as detached in `git worktree list`. `head-name` holds `refs/heads/<name>`; BISECT_START
    holds a bare branch name or a commit hash. A hash is kept as it is: it equals no branch name that matters."""
    asked = git(tree_path, "rev-parse", "--absolute-git-dir")
    if asked.returncode != 0:
        raise PruneError(f"git rev-parse --absolute-git-dir failed in {tree_path}: {asked.stderr.strip()}")
    git_dir = pathlib.Path(asked.stdout.strip())
    names = []
    for parts in REBASE_HEAD_NAME_FILES:
        head_name = read_git_dir_file(git_dir, parts)
        if head_name and head_name.startswith(HEADS_PREFIX):
            names.append(head_name[len(HEADS_PREFIX):])
    bisect_start = read_git_dir_file(git_dir, (BISECT_START_FILE,))
    if bisect_start:
        names.append(bisect_start)
    return names


def checked_out_branches(worktrees):
    """{branch: why it must stay} for every branch a worktree entry holds, or holds in a rebase or bisect."""
    taken = {}
    for tree in worktrees:
        if tree.branch:
            taken[tree.branch] = CHECKED_OUT_REASON
    for tree in worktrees:
        if tree.bare or tree.prunable or not os.path.isdir(tree.path):
            continue
        for name in branches_in_progress(tree.path):
            taken.setdefault(name, f"it is in a rebase or bisect in the worktree {show(tree.path)}")
    return taken


def merged_free_branches(repo):
    listed = git(repo.main_path, "for-each-ref", f"--merged={repo.compare_hash}", "--format=%(refname)", HEADS_PREFIX)
    if listed.returncode != 0:
        raise PruneError(f"git for-each-ref failed: {listed.stderr.strip()}")
    worktrees = list_worktrees(repo.main_path)
    taken = checked_out_branches(worktrees)
    names = [line[len(HEADS_PREFIX):] for line in listed.stdout.splitlines() if line.startswith(HEADS_PREFIX)]
    return sorted(name for name in names if name != repo.default_branch and name not in taken)


def delete_one_branch(repo, name, tally):
    if name == repo.default_branch:
        print(f"kept    branch {name}: it is the default branch")
        tally.kept += 1
        return
    try:
        worktrees = list_worktrees(repo.main_path)
        taken = checked_out_branches(worktrees)
    except PruneError as error:
        print(f"failed  branch {name}: the re-check could not read git state: {error}", flush=True)
        tally.failed += 1
        return
    if name in taken:
        print(f"kept    branch {name}: {taken[name]}")
        tally.kept += 1
        return
    outcome = delete_branch(repo, name)
    if outcome.failure is not None:
        print(f"failed  branch {name}: {outcome.failure}", flush=True)
        tally.failed += 1
        return
    print(f"deleted branch {name}")
    if outcome.warning is not None:
        print(outcome.warning)
    tally.removed += 1


def prune_branches(repo, apply):
    print(f"compare ref: {repo.compare_name} ({repo.compare_hash[:8]})")
    names = merged_free_branches(repo)
    for name in names:
        ahead = ahead_text(repo, name)
        print(f"delete  branch {name}{ahead}")
    print(f"would delete {len(names)} merged branches without a worktree")
    if not apply:
        return 0
    tally = Tally()
    for name in names:
        delete_one_branch(repo, name, tally)
    print(f"deleted {tally.removed}, kept {tally.kept}, failed {tally.failed}")
    return 1 if tally.failed else 0
