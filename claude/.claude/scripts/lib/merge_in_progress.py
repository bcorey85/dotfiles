"""merge_in_progress.py: whether every staged path in a folder is a path the open merge changed, so a bare
`git commit` there ends the merge."""
import sys

import script_utils

GIT_TIMEOUT_SECONDS = 10


def merge_heads(directory):
    """The commit ids in MERGE_HEAD of the worktree at `directory`: an empty list when no merge is open, None when
    git failed."""
    merge_head_file = script_utils.git_path(directory, "MERGE_HEAD")
    if merge_head_file is None:
        return None
    if not merge_head_file.is_file():
        return []
    return [line.strip() for line in merge_head_file.read_text().splitlines() if line.strip()]


def diff_name_set(directory, *diff_arguments):
    """The paths `git diff --name-only <diff_arguments>` names in `directory`, or None after a git failure, which
    is named on stderr."""
    paths = script_utils.diff_paths(directory, *diff_arguments, timeout=GIT_TIMEOUT_SECONDS)
    if paths is None:
        sys.stderr.write(f"[merge_in_progress] git diff {' '.join(diff_arguments)} failed in {directory}\n")
    return paths


def commit_ends_merge(directory):
    """True when a merge is open in `directory` and every staged path is a path the merged commits changed since
    they left HEAD: a bare `git commit` then takes no path outside the merge's changed paths. A peer's staged
    change to one of those paths is not told apart. Fail-closed: any git failure reads as False."""
    heads = merge_heads(directory)
    if heads is None:
        sys.stderr.write(f"[merge_in_progress] could not read MERGE_HEAD in {directory}\n")
        return False
    if not heads:
        return False
    staged_paths = diff_name_set(directory, "--cached")
    if staged_paths is None:
        return False
    merge_paths = set()
    for head in heads:
        changed = diff_name_set(directory, f"HEAD...{head}")
        if changed is None:
            return False
        merge_paths.update(changed)
    return staged_paths <= merge_paths
