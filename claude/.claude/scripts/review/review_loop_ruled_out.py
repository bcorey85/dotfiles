"""review_loop_ruled_out.py: the files the user ruled out of a review's scope. The loop never reviews one, sends no
finding on one to a coder, puts back a ruled-out file a coder pass changed, and restores a file of the diff under
review that a pass deleted with no finding naming the deletion."""
import pathlib
import re
import typing

import file_backup
import review_loop_held
import review_loop_untracked
import worktree_snapshot

RULED_OUT_REASON = "the user ruled the file out of scope"
# Under it, per coder role: `ruled-out/` copies the ruled-out files, `diff/` copies the files of the diff under review,
# `out-of-scope/` copies the dirty files outside the pass's scope.
BACKUP_FOLDER = "pass-backup"
# A move or rename takes the old path away, so a coder's `git mv` is a deletion of it that the finding names.
DELETION_WORD = r"(?:delet|remov|mov|renam)\w*"
# What stands before and after a path that a text holds as a whole token.
PATH_TOKEN_START = r"(?<![\w./-])"
PATH_TOKEN_END = r"(?![\w/-]|\.\w)"

# One note per coder pass that changed a ruled-out file or deleted a file of the diff, for the packet's tool_fault.
RULED_OUT_FAULTS = []


class RuledOutSplit(typing.NamedTuple):
    """kept: the items that name no ruled-out file. ruled: the ones that do. recorded: how many of those are new in
    skipped_fp."""

    kept: list
    ruled: list
    recorded: int


class RuledOutPutBack(typing.NamedTuple):
    """put_back: the ruled-out paths the guard restored or removed. left: the directories the pass created at ruled-out
    paths, which stay."""

    put_back: list
    left: list


def skip_ruled_out(items, ruled_out, skipped_fp, repo):
    """Splits `items` by whether they name a ruled-out file. Each ruled one goes into `skipped_fp` once, with the
    reason RULED_OUT_REASON, however many callers or rounds meet it."""
    kept, ruled, recorded = [], [], 0
    for item in items:
        if review_loop_held.held_path_of(item, ruled_out, set(), repo) is None:
            kept.append(item)
            continue
        ruled.append(item)
        if any(entry["item"] == item and entry["reason"] == RULED_OUT_REASON for entry in skipped_fp):
            continue
        skipped_fp.append({"item": item, "reason": RULED_OUT_REASON})
        recorded += 1
    return RuledOutSplit(kept, ruled, recorded)


def names_deletion(finding_texts, path, root):
    """Whether one of the finding texts asks to delete, remove, move or rename `path`: such a word, then the path as a
    whole token, or the path followed by "is/should be/can be deleted/removed". A path under `root` counts as `path`."""
    escaped = re.escape(path)
    as_object = rf"{DELETION_WORD}\s+(?:the\s+)?(?:file\s+)?`?{PATH_TOKEN_START}{escaped}`?{PATH_TOKEN_END}"
    as_subject = rf"{PATH_TOKEN_START}{escaped}`?\s+(?:is|should\s+be|can\s+be)\s+{DELETION_WORD}"
    pattern = re.compile(f"{as_object}|{as_subject}", re.IGNORECASE)
    root_prefix = f"{root}/"
    return any(pattern.search(text.replace(root_prefix, "")) for text in finding_texts)


class PassGuard:
    """What one coder pass must leave alone: a copy of each ruled-out file that existed before the pass, the paths
    that did not exist, and a copy of each file of the diff that no finding of the pass asks to delete."""

    def __init__(self, repo, role, ruled_backup, ruled_absent, backup, deletions):
        # The diff files a finding of the pass asks to delete: the untracked-file guard leaves them alone too.
        self.deletions = list(deletions)
        self.repo = pathlib.Path(repo)
        self.role = role
        self.ruled_backup = ruled_backup
        # Ruled-out files the backup could not copy: the hash each had before the pass, to tell a change afterwards.
        self.unsaved_hashes = {path: worktree_snapshot.file_hash(self.repo, path) for path in ruled_backup.unsaved}
        self.ruled_absent = ruled_absent
        self.backup = backup

    def put_back_ruled_out(self):
        """Copies back each ruled-out file that changed or vanished, and removes each file the pass created. A
        directory the pass created at a ruled-out path stays. Returns RuledOutPutBack(the paths put back, the
        directories left in place)."""
        put_back = file_backup.restore_changed(self.ruled_backup)
        left = []
        for path in self.ruled_absent:
            target = self.repo / path
            if not target.exists():
                continue
            if target.is_dir() and not target.is_symlink():
                left.append(path)
                continue
            target.unlink()
            put_back.append(path)
        return RuledOutPutBack(sorted(put_back), sorted(left))

    def changed_uncopied_files(self):
        """The ruled-out files the backup could not copy that the pass changed or deleted."""
        return sorted(path for path, before in self.unsaved_hashes.items()
                      if worktree_snapshot.file_hash(self.repo, path) != before)

    def undo(self):
        """Puts the ruled-out files back, restores the diff files the pass deleted, notes both, drops the backups."""
        put_back, left_in_place = self.put_back_ruled_out()
        uncopied = self.changed_uncopied_files()
        restored, lost = file_backup.restore_missing(self.backup)
        file_backup.discard(self.ruled_backup)
        file_backup.discard(self.backup)
        if put_back:
            RULED_OUT_FAULTS.append(f"{self.role} changed files the user ruled out of scope; the loop put them "
                                    "back: " + ", ".join(put_back))
        if left_in_place:
            RULED_OUT_FAULTS.append(f"{self.role} made directories at paths the user ruled out of scope; the loop "
                                    "left in place what it cannot remove safely, so check them: "
                                    + ", ".join(left_in_place))
        if uncopied:
            RULED_OUT_FAULTS.append(f"{self.role} changed files the user ruled out of scope that the loop could not "
                                    "copy, so the change stays: " + ", ".join(uncopied))
        if restored:
            RULED_OUT_FAULTS.append(f"{self.role} deleted files of the change under review with no finding that "
                                    "names the deletion; the loop restored " + ", ".join(restored))
        if lost:
            RULED_OUT_FAULTS.append(f"{self.role} deleted files of the change under review that the loop could not "
                                    "copy, so they are gone: " + ", ".join(lost))


def begin_pass(repo, out, role, ruled_out, diff_files, finding_texts):
    """The PassGuard of one coder pass. `diff_files` are the files of the diff under review; `finding_texts` are the
    pass's findings, whose text may name a deletion."""
    root = pathlib.Path(repo)
    pass_dir = pathlib.Path(out) / BACKUP_FOLDER / role
    ruled_backup = file_backup.save_files(root, ruled_out, pass_dir / "ruled-out")
    ruled_absent = sorted(path for path in ruled_out if not (root / path).exists())
    deletions = [path for path in diff_files if path not in ruled_out and names_deletion(finding_texts, path, root)]
    # The untracked-file guard around the model call puts back and notes an untracked file it covers; this guard
    # backs up only the rest, so one deletion makes one note.
    covered = review_loop_untracked.guarded_untracked(root, deletions)
    kept_paths = [path for path in diff_files
                  if path not in ruled_out and path not in deletions and path not in covered]
    backup = file_backup.save_files(root, kept_paths, pass_dir / "diff")
    return PassGuard(root, role, ruled_backup, ruled_absent, backup, deletions)
