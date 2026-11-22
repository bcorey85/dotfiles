"""review_loop_scope_guard.py: the files a fix pass must leave alone because they sit outside the review's scope. After
each coder pass the loop puts back every file the pass changed that existed before it, that the pass's scope does not
hold and that no finding of the pass names, and notes which. A file the pass created stays."""
import pathlib
import re
import typing

import file_backup
import script_utils
import worktree_snapshot
from review_loop_ruled_out import BACKUP_FOLDER, PATH_TOKEN_END, PATH_TOKEN_START, texts_relative_to

# One note per coder pass that changed a file outside the review scope, for the packet's tool_fault.
SCOPE_FAULTS = []


def findings_name(finding_texts, path, root):
    """Whether one of the finding texts holds `path` as a whole token. A path under `root` counts as `path`."""
    pattern = re.compile(f"{PATH_TOKEN_START}{re.escape(path)}{PATH_TOKEN_END}")
    return any(pattern.search(text) for text in texts_relative_to(finding_texts, root))


class PassScope(typing.NamedTuple):
    """What one coder pass may change: the `allowed` paths, the paths `has_own_guard` is true for (another guard of
    the loop rules on those) and the paths its findings name."""

    root: pathlib.Path
    allowed: frozenset
    has_own_guard: typing.Callable
    finding_texts: tuple

    def holds(self, path):
        """Whether the pass may change `path`."""
        if path in self.allowed or self.has_own_guard(path):
            return True
        return findings_name(self.finding_texts, path, self.root)


def paths_differing_from_head(repo, head, *diff_options):
    """The paths whose work tree or index text differs from `head` (a deleted file and both sides of a rename
    included), as a set. A rename is listed by both paths because renames are not detected. `diff_options` narrow
    the listing."""
    if head is None:
        return set()
    listing = script_utils.git_output(repo, "diff", "--name-only", "-z", "--no-renames", *diff_options, head)
    if listing is None:
        raise RuntimeError(f"scope guard: `git diff {head}` failed in {repo}")
    return {path for path in listing.split("\0") if path}


class ScopeGuard:
    """The files outside one coder pass's `scope`. `backup` copies the dirty ones among them; `dirty_before` holds
    every path that already differed from `head` before the pass; `head` is the commit HEAD named then, which holds
    the text of every other tracked file."""

    def __init__(self, role, scope, backup, head, dirty_before):
        self.repo = scope.root
        self.role = role
        self.scope = scope
        self.backup = backup
        self.dirty_before = dirty_before
        # Dirty files the backup could not copy: the hash each had before the pass, to tell a change afterwards.
        self.unsaved_hashes = {path: worktree_snapshot.file_hash(self.repo, path) for path in backup.unsaved}
        self.head = head

    def changed_clean_files(self):
        """The tracked files that were clean before the pass, differ from `head` now and the pass may not change."""
        changed_now = paths_differing_from_head(self.repo, self.head, "--diff-filter=MDT")
        changed = changed_now - self.dirty_before
        return sorted(path for path in changed if not self.scope.holds(path))

    def put_back_clean_files(self):
        """Restores each such file, in the work tree and the index, to its text in `head`. Returns the paths."""
        paths = self.changed_clean_files()
        if not paths:
            return []
        restored = script_utils.git_output(self.repo, "--literal-pathspecs", "restore", f"--source={self.head}",
                                           "--staged", "--worktree", "--", *paths)
        if restored is None:
            raise RuntimeError(f"scope guard: `git restore --source={self.head}` failed in {self.repo} for "
                               + ", ".join(paths))
        return paths

    def undo(self):
        """Puts back the files outside the scope that the pass changed, notes them, drops the backup."""
        put_back = file_backup.restore_changed(self.backup)
        uncopied = sorted(path for path, before in self.unsaved_hashes.items()
                          if worktree_snapshot.file_hash(self.repo, path) != before)
        file_backup.discard(self.backup)
        put_back = sorted([*put_back, *self.put_back_clean_files()])
        if put_back:
            SCOPE_FAULTS.append(f"{self.role} changed files outside the review scope that no finding names; the "
                                "loop put them back: " + ", ".join(put_back))
        if uncopied:
            SCOPE_FAULTS.append(f"{self.role} changed files outside the review scope that the loop could not copy, "
                                "so the change stays: " + ", ".join(uncopied))


def guard_pass(repo, out, role, allowed, has_own_guard, finding_texts):
    """The ScopeGuard of one coder pass. `allowed` are the paths the pass may change, `has_own_guard(path)` says
    whether another guard of the loop rules on a path, and `finding_texts` are the pass's findings, whose text may
    name more paths."""
    root = pathlib.Path(repo)
    scope = PassScope(root, frozenset(allowed), has_own_guard, tuple(finding_texts))
    dirty = [path for path in worktree_snapshot.status_codes(root) if not scope.holds(path)]
    backup = file_backup.save_files(root, dirty, pathlib.Path(out) / BACKUP_FOLDER / role / "out-of-scope")
    head = script_utils.head_commit(root)
    return ScopeGuard(role, scope, backup, head, paths_differing_from_head(root, head))
