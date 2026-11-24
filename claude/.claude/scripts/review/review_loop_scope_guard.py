"""review_loop_scope_guard.py: the files a fix pass must leave alone because they sit outside the review's scope. After
each coder pass the loop puts back every tracked or untracked file (not a gitignored one) the pass changed that existed
before it, that the pass's scope does not hold and that no finding of the pass names, and notes which. A file the
pass created stays. The guard does not undo a commit the coder makes during the pass: the work tree and index go
back, HEAD keeps the commit."""
import pathlib
import typing

import file_backup
import script_utils
import worktree_snapshot
from review_loop_ruled_out import BACKUP_FOLDER

# The notes for the packet's tool_fault: a pass adds one for the files put back, one for a failed put-back step and
# one for the files the loop could not copy.
SCOPE_FAULTS = []

DIRTY_FILES_STEP = "dirty files"
INDEX_ENTRIES_STEP = "index entries"
CLEAN_FILES_STEP = "clean files"


class PassScope(typing.NamedTuple):
    """What one coder pass may change: the `allowed` paths, the paths `has_own_guard` is true for (another guard of
    the loop rules on those) and the paths its findings name. `repo_files` is a callable that returns the repo's
    files, for the trailing-part rule."""

    root: pathlib.Path
    allowed: frozenset
    has_own_guard: typing.Callable
    finding_texts: tuple
    repo_files: typing.Callable

    def holds(self, path):
        """Whether the pass may change `path`: a finding names it in full, with a `./` prefix, or by a trailing part
        of its path, with a `/` or a `.` in it, that no other repo file ends with. Only the last rule calls
        `repo_files`."""
        if path in self.allowed or self.has_own_guard(path):
            return True
        if script_utils.texts_name_path(self.finding_texts, path, self.root):
            return True
        return script_utils.texts_name_path_by_suffix(self.finding_texts, path, self.root, self.repo_files())


class RepoFileListing:
    """The repo's files as `git ls-files` lists them, taken on the first call and kept for the later ones. A failed
    listing raises GitCallError."""

    def __init__(self, root):
        self.root = root
        self.files = None

    def __call__(self):
        if self.files is not None:
            return self.files
        self.files = frozenset(script_utils.repo_file_paths_or_raise(self.root))
        return self.files


def paths_differing_from_head(repo, head, *diff_options):
    """The paths whose work tree text differs from `head` (with `--cached` in `diff_options`, whose index entry
    differs), a deleted file and both sides of a rename included, as a set. A rename is listed by both paths because
    renames are not detected. Other `diff_options` narrow the listing."""
    if head is None:
        return set()
    listing = script_utils.git_output(repo, "diff", "--name-only", "-z", "--no-renames", *diff_options, head)
    if listing is None:
        raise script_utils.GitCallError(f"scope guard: `git diff {head}` failed in {repo}")
    return {path for path in listing.split("\0") if path}


class PassStart(typing.NamedTuple):
    """What the repo held before the pass. `backup` copies the dirty files outside the scope; `index_entries` is the
    index entry each of them had (None for a path not in the index); `head` is the commit HEAD named then, which holds
    the text of every other tracked file; `dirty_before` holds every path that already differed from `head`."""

    backup: typing.Any
    index_entries: dict
    head: str | None
    dirty_before: set


class ScopeGuard:
    """The files outside one coder pass's `scope`, and the state of the repo `before` the pass."""

    def __init__(self, role, scope, before, put_back_dir):
        self.repo = scope.root
        self.role = role
        self.scope = scope
        self.backup = before.backup
        self.index_entries = before.index_entries
        self.dirty_before = before.dirty_before
        # Dirty files the backup could not copy: the hash each had before the pass, to tell a change afterwards.
        self.unsaved_hashes = {path: worktree_snapshot.file_hash(self.repo, path) for path in before.backup.unsaved}
        self.changed_unsaved = None
        self.head = before.head
        # Where the work tree bytes the guard overwrites are kept: the guard cannot tell who wrote them (the pass, the
        # user in an editor, another session). Never discarded. A replaced index entry is not copied there: its blob
        # stays in git's object store until `git gc` prunes it (two weeks by default), and the fault note names its id.
        self.put_back_dir = put_back_dir
        # The paths put back so far in this undo, so a step that fails later still leaves them noted.
        self.put_back_paths = set()
        # The paths whose overwritten work tree bytes could not be kept, and the index blob each replaced entry had.
        self.unkept_paths = set()
        self.replaced_blobs = {}
        self.failed = False
        # The step `undo` ran last, to say what a failure left behind.
        self.current_step = None

    def keep_bytes_of(self, paths):
        """Copies the work tree bytes of `paths` under the put-back folder, before the guard overwrites them. Returns
        the paths whose bytes are kept; a path the loop could not copy is left as it is, so no bytes are lost."""
        unsaved = set(file_backup.save_files(self.repo, paths, self.put_back_dir).unsaved)
        self.unkept_paths.update(unsaved)
        return [path for path in paths if path not in unsaved]

    def put_back_dirty_files(self):
        """Copies each dirty file the pass changed back from the backup, keeping the bytes it overwrites."""
        overwritten = self.keep_bytes_of(file_backup.saved_paths_that_differ(self.backup))
        # One path at a time, so a copy that fails partway still leaves the paths already put back noted.
        for path in overwritten:
            self.put_back_paths.update(file_backup.restore_paths(self.backup, [path]))

    def put_back_dirty_index_entries(self):
        """Puts the index entry of each dirty file outside the scope back to what it was before the pass: the backup
        copies bytes only, so a `git add` of the pass would stay."""
        entries_now = script_utils.index_entries(self.repo, list(self.index_entries))
        # A file the loop holds no copy of and whose text the pass changed keeps its pass text, so its index entry stays
        # too.
        left_alone = self.unkept_paths | self.changed_unsaved_paths()
        changed = [path for path, entry in self.index_entries.items() if entries_now[path] != entry
                   and path not in left_alone]
        for path in changed:
            if not script_utils.restore_index_entry(self.repo, path, self.index_entries[path]):
                raise script_utils.GitCallError(
                    f"scope guard: restoring the index entry of {path} failed in {self.repo}")
            self.note_replaced_blobs([path], entries_now)
            self.put_back_paths.add(path)

    def note_replaced_blobs(self, paths, entries_now):
        """Records the blob id of the index entry each of `paths` holds now, which the put-back replaces."""
        for path in paths:
            entry = entries_now[path]
            if entry is not None:
                self.replaced_blobs[path] = entry.blob

    def changed_clean_files(self):
        """The tracked files that were clean before the pass, differ from `head` now and the pass may not change."""
        changed_now = paths_differing_from_head(self.repo, self.head, "--diff-filter=MDT")
        changed = changed_now - self.dirty_before
        return sorted(path for path in changed if not self.scope.holds(path))

    def put_back_clean_files(self):
        """Restores each such file, in the work tree and the index, to its text in `head`, keeping the bytes it
        overwrites."""
        paths = self.keep_bytes_of(self.changed_clean_files())
        if not paths:
            return
        staged = sorted(set(paths) & paths_differing_from_head(self.repo, self.head, "--cached"))
        staged_entries = script_utils.index_entries(self.repo, staged)
        restored = script_utils.git_output(self.repo, "--literal-pathspecs", "restore", f"--source={self.head}",
                                           "--staged", "--worktree", "--", *paths)
        if restored is None:
            raise script_utils.GitCallError(f"scope guard: `git restore --source={self.head}` failed in {self.repo} "
                                            "for " + ", ".join(paths))
        self.note_replaced_blobs(staged, staged_entries)
        self.put_back_paths.update(paths)

    def undo(self):
        """Puts back the files outside the scope that the pass changed, notes them, drops the backup. The files put
        back before a step fails are noted too, and the backup stays when any step failed (the note says where each
        failed step's pre-pass state is kept)."""
        try:
            self.current_step = DIRTY_FILES_STEP
            self.put_back_dirty_files()
            self.current_step = INDEX_ENTRIES_STEP
            self.put_back_dirty_index_entries()
            self.current_step = CLEAN_FILES_STEP
            self.put_back_clean_files()
        except Exception:
            self.failed = True
            raise
        finally:
            self.note_faults()

    def not_put_back_hint(self):
        """Where the pre-pass state of what the failed step left is kept."""
        entries = (f"{path}={entry.blob if entry else 'not in the index'}"
                   for path, entry in sorted(self.index_entries.items()))
        entries_clause = "the index entries before the pass were: " + ", ".join(entries)
        # With no commit the guard handles no clean file, so no step leaves one unrestored.
        clean_clause = ""
        if self.head is not None:
            clean_clause = ("; any clean file the pass changed stays unrestored; its pre-pass text is in commit "
                            + self.head)
        # The path whose copy raised may be half-written and is not in put_back_paths, so the put-back note may not
        # name the folder.
        kept_clause = ""
        if self.put_back_dir.exists():
            kept_clause = f"; the work tree bytes of the files it was putting back are copied to {self.put_back_dir}"
        if self.current_step == DIRTY_FILES_STEP:
            return (f"the pre-pass copies of the dirty files not put back stay in {self.backup.backup_dir}"
                    f"{kept_clause}; any index entry the pass changed stays unrestored; "
                    f"{entries_clause}{clean_clause}")
        if self.current_step == INDEX_ENTRIES_STEP:
            return f"the dirty files the loop could copy are back{kept_clause}; {entries_clause}{clean_clause}"
        return (f"the dirty files the loop could copy are back{kept_clause}; "
                f"the pre-pass text of the clean files not put back is in commit {self.head}")

    def changed_unsaved_paths(self):
        """The files the backup could not copy whose work tree text the pass changed. Hashed once per guard: the
        files are over the copy cap or unreadable, so each read is costly or fails the same way."""
        if self.changed_unsaved is None:
            self.changed_unsaved = {path for path, before in self.unsaved_hashes.items()
                                    if worktree_snapshot.file_hash(self.repo, path) != before}
        return self.changed_unsaved

    def note_faults(self):
        """Notes in SCOPE_FAULTS the files put back, a failed step and where its pre-pass state is kept, and the files
        it could not copy (their change stays); drops the backup when every step succeeded."""
        uncopied = sorted(self.changed_unsaved_paths() | self.unkept_paths)
        if self.put_back_paths:
            note = (f"{self.role} changed files outside the review scope that no finding names; the loop put them "
                    "back: " + ", ".join(sorted(self.put_back_paths)))
            if self.put_back_dir.exists():
                note += f"; the work tree bytes of the files it was putting back are copied to {self.put_back_dir}"
            if self.replaced_blobs:
                blobs = (f"{path}={blob}" for path, blob in sorted(self.replaced_blobs.items()))
                note += ("; replaced index blobs (read with `git cat-file -p` until `git gc` prunes them, two weeks by "
                         "default): " + ", ".join(blobs))
            SCOPE_FAULTS.append(note)
        if self.failed:
            SCOPE_FAULTS.append(f"{self.role} could not finish putting back files outside the review scope; "
                                + self.not_put_back_hint())
        else:
            file_backup.discard(self.backup)
        if uncopied:
            SCOPE_FAULTS.append(f"{self.role} changed files outside the review scope that the loop could not copy, "
                                "so the change stays: " + ", ".join(uncopied))


def guard_pass(repo, out, role, allowed, has_own_guard, finding_texts):
    """The ScopeGuard of one coder pass. `allowed` are the paths the pass may change, `has_own_guard(path)` says
    whether another guard of the loop rules on a path, and `finding_texts` are the pass's findings, whose text may
    name more paths. The repo's files are listed the first time any path reaches the trailing-part rule: a path dirty
    before the pass (here) or a clean file the pass changed (in `undo`). A failed listing raises GitCallError; in
    `undo` it stops the loop as an undo-failure CoderCallError."""
    root = pathlib.Path(repo)
    scope = PassScope(root, frozenset(allowed), has_own_guard, tuple(finding_texts), RepoFileListing(root))
    dirty = [path for path in worktree_snapshot.status_codes(root, strict=True) if not scope.holds(path)]
    pass_dir = pathlib.Path(out) / BACKUP_FOLDER / role
    index_entries = script_utils.index_entries(root, dirty)
    head = script_utils.head_commit_or_unborn(root)
    dirty_before = paths_differing_from_head(root, head)
    backup = file_backup.save_files(root, dirty, pass_dir / "out-of-scope")
    start = PassStart(backup, index_entries, head, dirty_before)
    # The same role runs twice in one loop, and each guard keeps its own bytes in a folder no earlier guard used.
    put_back_dir = script_utils.next_numbered_dir(pass_dir / "put-back")
    return ScopeGuard(role, scope, start, put_back_dir)
