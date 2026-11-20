"""review_loop_untracked.py: the guard around every model call of the review loop. A call may edit an untracked file
but never delete one that no coder of this loop wrote. The guard copies the untracked files to the loop's out folder
before the call, puts back each one the call removed, and notes which call removed what."""
import pathlib
import shutil
import tempfile
import typing

import file_backup
import script_utils

# One note per model call that deleted an untracked file no coder of this loop made, for the packet's tool_fault.
UNTRACKED_FAULTS = []
# The untracked files an earlier coder call of this loop wrote. A later call may delete one, so it is neither backed up
# nor put back. A file anyone else writes while a coder call runs counts as that call's file.
LOOP_WRITTEN = set()
BACKUP_FOLDER = "untracked-backup"


def untracked_set(repo):
    """The untracked paths in the work tree. Raises when git fails: the guard never goes on with an empty set."""
    paths = script_utils.untracked_paths(repo)
    if paths is None:
        raise RuntimeError(f"untracked-file guard: git ls-files failed in {repo}")
    return set(paths)


def unheld_untracked(repo, held):
    """The untracked paths in the work tree that `held` does not name. The set taken before a coder call and the one
    taken after it both come from here."""
    return untracked_set(repo) - set(held)


def record_loop_written(repo, held, untracked_before):
    """Adds the untracked files present now that were not there before the call to LOOP_WRITTEN, and drops the
    recorded files that are gone."""
    untracked_after = unheld_untracked(repo, held)
    LOOP_WRITTEN.update(untracked_after - untracked_before)
    LOOP_WRITTEN.intersection_update(untracked_after)


class CallRemoval(typing.NamedTuple):
    """What a model call removed: `restored` paths the guard put back, `lost` paths it could not."""

    restored: list
    lost: list


class CallGuard:
    """The untracked files copied before one model call."""

    def __init__(self, backup):
        self.backup = backup

    def restore(self):
        """Puts back the copied files the call removed and deletes the copies."""
        restored, lost = file_backup.restore_missing(self.backup)
        file_backup.discard(self.backup)
        return CallRemoval(restored, lost)


def guarded_untracked(repo, deletable=()):
    """The untracked files the guard copies and puts back: no coder of this loop wrote them and no finding of the pass
    asks to delete them (`deletable`). A file another session holds is guarded too."""
    return untracked_set(repo) - LOOP_WRITTEN - set(deletable)


def begin(repo, out, deletable=()):
    """Copies the guarded untracked files (see guarded_untracked) to a new folder under `out`."""
    backup_root = pathlib.Path(out) / BACKUP_FOLDER
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_dir = pathlib.Path(tempfile.mkdtemp(dir=backup_root))
    try:
        guarded = guarded_untracked(repo, deletable)
        backup = file_backup.save_files(repo, guarded, backup_dir)
    except BaseException:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    return CallGuard(backup)


def note_removal(call_label, removal):
    """Adds the tool_fault notes for a call that removed untracked files. `call_label` names the call:
    `call-NN-<role>`, the bare role for a call that died before it got a number, or `review<N>-main` for a
    main-session reviewer round."""
    if removal.restored:
        UNTRACKED_FAULTS.append(f"{call_label} deleted untracked files that no coder of this loop made; the loop "
                                "restored " + ", ".join(removal.restored))
    if removal.lost:
        UNTRACKED_FAULTS.append(f"{call_label} deleted untracked files the loop could not copy (over "
                                f"{file_backup.MAX_FILE_BYTES // (1024 * 1024)} MB or unreadable), so they are gone: "
                                + ", ".join(removal.lost))
