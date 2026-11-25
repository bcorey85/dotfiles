"""Copy a set of files to a folder on disk before a step that may delete them, and put back the ones that vanished or,
through restore_changed or restore_paths, the ones that changed. put_back_all does both, and also deletes the paths
the caller names as created and the paths that did not exist when saved.

It knows nothing about the files: the caller names the paths and the folder for the copies. A file over the size cap,
or one that cannot be read, is not copied, so its loss can be reported but not undone."""
import pathlib
import shutil

MAX_FILE_BYTES = 50 * 1024 * 1024


class Backup:
    """saved: the paths copied. unsaved: the paths left out, over the cap or unreadable. absent: the paths that did not
    exist when saved. Each saved path's copy sits at backup_dir/<path>."""

    def __init__(self, root, backup_dir, saved, unsaved, absent=()):
        self.root = pathlib.Path(root)
        self.backup_dir = pathlib.Path(backup_dir)
        self.saved = saved
        self.unsaved = unsaved
        self.absent = sorted(absent)


def save_files(root, paths, backup_dir, max_file_bytes=MAX_FILE_BYTES):
    """Copy each existing regular file in `paths` (relative to `root`) under `backup_dir`, up to the per-file cap."""
    root = pathlib.Path(root)
    backup_dir = pathlib.Path(backup_dir)
    saved = []
    unsaved = []
    for path in sorted(paths):
        source = root / path
        if not source.is_file():
            continue

        try:
            if source.stat().st_size > max_file_bytes:
                unsaved.append(path)
                continue

            copy = backup_dir / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copy)
        except OSError:
            unsaved.append(path)
            continue

        saved.append(path)
    absent = [path for path in paths if not (root / path).exists()]
    return Backup(root, backup_dir, saved, unsaved, absent)


def restore_missing(backup):
    """Copy back every saved file that is no longer there. Returns (restored, lost): the paths put back, and the
    unsaved paths that are gone, which could not be."""
    restored = []
    for path in backup.saved:
        target = backup.root / path
        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup.backup_dir / path, target)
        restored.append(path)
    lost = [path for path in backup.unsaved if not (backup.root / path).exists()]
    return sorted(restored), sorted(lost)


def saved_paths_that_differ(backup):
    """The sorted saved paths whose file is missing or whose bytes differ from the copy."""
    differing = []
    for path in backup.saved:
        target = backup.root / path
        copy = backup.backup_dir / path
        if target.is_file() and target.read_bytes() == copy.read_bytes():
            continue
        differing.append(path)
    return sorted(differing)


def restore_changed(backup):
    """Copy back every saved file that is missing or whose bytes differ from its copy, with its mode bits. Returns
    the sorted paths put back."""
    return restore_paths(backup, saved_paths_that_differ(backup))


def restore_paths(backup, paths):
    """Copy back each of `paths` (saved ones) from its copy, with its mode bits. Returns them sorted."""
    restored = sorted(paths)
    for path in restored:
        target = backup.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup.backup_dir / path, target)
    return restored


def put_back_all(backup, created=()):
    """Copy back every saved file that changed or vanished, and unlink each path of backup.absent and `created` that
    exists now. A real directory at such a path stays. Returns (put_back, left): the sorted paths put back or
    removed, and the sorted directories left in place."""
    put_back = restore_changed(backup)
    left = []
    for path in {*backup.absent, *created}:
        target = backup.root / path
        if not target.exists():
            continue
        if target.is_dir() and not target.is_symlink():
            left.append(path)
            continue
        target.unlink()
        put_back.append(path)
    return sorted(put_back), sorted(left)


def discard(backup):
    """Delete the copies."""
    shutil.rmtree(backup.backup_dir, ignore_errors=True)
