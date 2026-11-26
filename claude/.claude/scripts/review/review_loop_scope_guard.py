"""review_loop_scope_guard.py: the files a fix pass must leave alone because they sit outside the review's scope. After
each coder pass the loop puts back every tracked or untracked file (not a gitignored one) the pass changed that existed
before it, that the pass's scope does not hold and that no finding of the pass names, and notes which. A file the
pass created stays. The guard does not undo a commit the coder makes during the pass: the work tree and index go
back, HEAD keeps the commit. A put-back file is then judged by the pass's gate: one the fix needs (the gate fails
without it and passes with it) is kept; for any other the guard sets `stray_blocker`, which stops the loop."""
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
KEEP_NEEDED_STEP = "kept files"


class PassScope(typing.NamedTuple):
    """What one coder pass may change: the `allowed` paths, the paths `has_own_guard` is true for (another guard of
    the loop rules on those) and the paths its findings name. `repo_files` is the repo's files before the pass, as
    a frozenset, for the trailing-part rule."""

    root: pathlib.Path
    allowed: frozenset
    has_own_guard: typing.Callable
    finding_texts: tuple
    repo_files: frozenset

    def holds(self, path):
        """Whether the pass may change `path`: a finding names it in full, with a `./` prefix, or by a trailing part
        of its path, with a `/` or a `.` in it, that no other repo file ends with."""
        if path in self.allowed or self.has_own_guard(path):
            return True
        return script_utils.texts_name_repo_file(self.finding_texts, path, self.root, self.repo_files)


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

    def __init__(self, role, scope, before, put_back_dir, gate_passes):
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
        # The paths whose pass bytes sit in the put-back folder. `gate_passes` runs the pass's gate
        # and returns True, False, or None when no gate runs. `stray_blocker` is why the loop must stop over the files
        # put back; None when none was put back or each was kept because the fix needs it.
        self.saved_paths = set()
        # The paths the pass deleted: the put-back folder holds no bytes for them, so the gate's "with it" state is the
        # file gone.
        self.deleted_paths = set()
        self.gate_passes = gate_passes
        self.stray_blocker = None
        # The strays `keep_needed_files` has copied back, so a failure partway names which carry the pass's bytes.
        self.restored_strays = []

    def keep_bytes_of(self, paths):
        """Copies the work tree bytes of `paths` under the put-back folder, before the guard overwrites them. Returns
        the paths the loop can overwrite: those whose bytes are kept and those the pass deleted (no bytes to keep). A
        path the loop could not copy is left as it is, so no bytes are lost."""
        saved = file_backup.save_files(self.repo, paths, self.put_back_dir)
        unsaved = set(saved.unsaved)
        self.unkept_paths.update(unsaved)
        self.saved_paths.update(saved.saved)
        self.deleted_paths.update(saved.absent)
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

    def put_back_everything(self):
        """The three put-back steps, in order."""
        self.current_step = DIRTY_FILES_STEP
        self.put_back_dirty_files()
        self.current_step = INDEX_ENTRIES_STEP
        self.put_back_dirty_index_entries()
        self.current_step = CLEAN_FILES_STEP
        self.put_back_clean_files()

    def stray_files(self):
        """The sorted files put back whose pass state the guard can restore (bytes saved, or deleted)."""
        return sorted((self.saved_paths | self.deleted_paths) & self.put_back_paths)

    def stray_blocker_text(self, strays, reason):
        """The stop text for the put-back `strays`: each file, why the loop stops, the folder with the pass bytes and
        the files the pass deleted. `reason` holds `{it}` where it names the files, `{each}` for "it" or
        "each of them"."""
        pronoun = "it" if len(strays) == 1 else "them"
        each = "it" if len(strays) == 1 else "each of them"
        text = (f"{self.role} changed {', '.join(strays)} outside the review scope and "
                f"{reason.format(it=pronoun, each=each)}; the loop put {pronoun} back")
        deleted = [path for path in strays if path in self.deleted_paths]
        if len(deleted) < len(strays):
            text += f" and kept the pass's bytes in {self.put_back_dir}"
        if deleted:
            text += f"; the pass deleted {', '.join(deleted)}"
        return text

    def restore_pass_state(self, strays):
        """Puts each stray back as the pass left it: its saved bytes copied back, a file the pass deleted removed.
        `restored_strays` then lists the strays that carry the pass's bytes."""
        self.restored_strays = []
        for path in strays:
            if path in self.deleted_paths:
                (self.repo / path).unlink(missing_ok=True)
            else:
                file_backup.restore_paths(file_backup.Backup(self.repo, self.put_back_dir, [], []), [path])
            self.restored_strays.append(path)

    def stop_on_strays(self, strays, reason):
        """Puts every stray back and sets the stop text for `strays` (reason as in `stray_blocker_text`)."""
        self.put_back_everything()
        self.stray_blocker = self.stray_blocker_text(strays, reason)

    def needed_strays(self, strays):
        """The strays the gate needs, judged each alone: the gate runs with every other stray in the pass's state and
        this one put back, and fails only when the fix needs this one. Returns None when a run gave no result. Leaves
        every stray put back when it judges two or more and every run gave a result; with one stray it returns it as
        is, still in the pass's state."""
        if len(strays) == 1:
            return strays
        needed = []
        for stray in strays:
            self.put_back_everything()
            self.current_step = KEEP_NEEDED_STEP
            self.restore_pass_state([other for other in strays if other != stray])
            passes_without_it = self.gate_passes()
            if passes_without_it is None:
                return None
            if not passes_without_it:
                needed.append(stray)
        self.put_back_everything()
        self.current_step = KEEP_NEEDED_STEP
        return needed

    def keep_files_as_needed(self, needed):
        """Restores the pass's state of `needed` strays, which stay, and notes them."""
        self.current_step = KEEP_NEEDED_STEP
        self.restore_pass_state(needed)
        self.put_back_paths.difference_update(needed)
        note = (f"{self.role} changed files outside the review scope that the fix needs (the gate "
                "fails with each of them put back alone and passes with every stray restored); the loop kept: "
                + ", ".join(needed))
        # Only the work tree bytes of a kept file are copied back; its replaced index blob is the only record of what
        # the pass staged.
        kept_blobs = [f"{path}={self.replaced_blobs[path]}" for path in needed if path in self.replaced_blobs]
        if kept_blobs:
            note += ("; the index entry the pass staged was replaced (blob read with `git cat-file -p` until "
                     "`git gc` prunes it): " + ", ".join(kept_blobs))
        SCOPE_FAULTS.append(note)

    def keep_needed_files(self):
        """Judges the files just put back with the pass's gate. Gate passes with them put back: the fix does not need
        them, so the loop stops. Gate fails with them put back and passes with the pass's bytes restored: each is then
        judged alone (see `needed_strays`); the needed ones stay, noted, and the loop stops over the rest. Otherwise
        they go back again and the loop stops. With no gate that runs, it stops too."""
        strays = self.stray_files()
        if not strays:
            return
        self.current_step = KEEP_NEEDED_STEP
        passes_without = self.gate_passes()
        if passes_without is None:
            self.stray_blocker = self.stray_blocker_text(strays, "no gate ran to show that the fix needs {it}")
            return
        if passes_without:
            self.stray_blocker = self.stray_blocker_text(strays, "the gate passes without {it}")
            return
        self.restore_pass_state(strays)
        passes_with = self.gate_passes()
        if passes_with is None:
            self.stop_on_strays(strays, "no gate ran with {it} to show that the fix needs {it}")
            return
        if not passes_with:
            self.stop_on_strays(strays, "the gate fails with {it} and without {it}")
            return
        needed = self.needed_strays(strays)
        if needed is None:
            self.stop_on_strays(strays, "no gate ran with {it} put back one at a time")
            return
        if not needed:
            self.stray_blocker = self.stray_blocker_text(
                strays, "the gate fails without all of {it} but passes with any one of {it} put back")
            return
        not_needed = [path for path in strays if path not in needed]
        self.keep_files_as_needed(needed)
        if not_needed:
            self.stray_blocker = self.stray_blocker_text(not_needed, "the gate passes with {each} put back alone")

    def undo(self, judge=True):
        """Puts back the files outside the scope that the pass changed, notes them, drops the backup. The files put
        back before a step fails are noted too, and the backup stays when any step failed (the note says where each
        failed step's pre-pass state is kept). A file the pass's gate shows the fix needs is kept; any other file put
        back sets `stray_blocker`. With `judge` false (the pass failed, so nothing reads a verdict) the files are only
        put back."""
        try:
            self.put_back_everything()
            if judge:
                self.keep_needed_files()
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
        if self.current_step == KEEP_NEEDED_STEP:
            restored = ", ".join(self.restored_strays) or "none"
            clean_copies = f"; the pre-pass text of a clean file is in commit {self.head}" if self.head else ""
            return (f"the files put back were being judged by the gate; their pre-pass copies of dirty files are in "
                    f"{self.backup.backup_dir}{clean_copies}; the pass's bytes of those it could restore are in "
                    f"{self.put_back_dir}; copied back to the work tree before the failure: {restored}")
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
            put_back_blobs = {path: blob for path, blob in self.replaced_blobs.items() if path in self.put_back_paths}
            if put_back_blobs:
                blobs = (f"{path}={blob}" for path, blob in sorted(put_back_blobs.items()))
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


def guard_pass(repo, out, role, allowed, has_own_guard, finding_texts, gate_passes):
    """The ScopeGuard of one coder pass. `allowed` are the paths the pass may change, `has_own_guard(path)` says
    whether another guard of the loop rules on a path, `finding_texts` are the pass's findings, whose text may
    name more paths, and `gate_passes()` runs the pass's gate. The repo's files are listed here, before the pass
    runs, so every later `holds` reads the pre-pass file set. A failed listing raises GitCallError."""
    root = pathlib.Path(repo)
    repo_files = frozenset(script_utils.repo_file_paths_or_raise(root))
    scope = PassScope(root, frozenset(allowed), has_own_guard, tuple(finding_texts), repo_files)
    dirty = [path for path in worktree_snapshot.status_codes(root, strict=True) if not scope.holds(path)]
    pass_dir = pathlib.Path(out) / BACKUP_FOLDER / role
    index_entries = script_utils.index_entries(root, dirty)
    head = script_utils.head_commit_or_unborn(root)
    dirty_before = paths_differing_from_head(root, head)
    backup = file_backup.save_files(root, dirty, pass_dir / "out-of-scope")
    start = PassStart(backup, index_entries, head, dirty_before)
    # The same role runs twice in one loop, and each guard keeps its own bytes in a folder no earlier guard used.
    put_back_dir = script_utils.next_numbered_dir(pass_dir / "put-back")
    return ScopeGuard(role, scope, start, put_back_dir, gate_passes)
