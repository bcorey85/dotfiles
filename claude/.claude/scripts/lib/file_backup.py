"""Save the bytes of a set of files before a step that may delete them, and put back the ones that vanished.

It knows nothing about the files: the caller names the paths. A file over the size cap is not saved, so its loss can
be reported but not undone. The whole save stays under a total cap too."""
import pathlib

MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024


class Backup:
    """saved: {path: bytes} of the files copied. unsaved: the paths left out, over a cap or unreadable."""

    def __init__(self, root, saved, unsaved):
        self.root = pathlib.Path(root)
        self.saved = saved
        self.unsaved = unsaved


def save_files(root, paths, max_file_bytes=MAX_FILE_BYTES, max_total_bytes=MAX_TOTAL_BYTES):
    """Copy the bytes of each existing regular file in `paths` (relative to `root`), within the caps."""
    root = pathlib.Path(root)
    saved = {}
    unsaved = []
    total = 0
    for path in sorted(paths):
        target = root / path
        if not target.is_file():
            continue

        try:
            size = target.stat().st_size
            if size > max_file_bytes or total + size > max_total_bytes:
                unsaved.append(path)
                continue

            saved[path] = target.read_bytes()
        except OSError:
            unsaved.append(path)
            continue

        total += size
    return Backup(root, saved, unsaved)


def restore_missing(backup):
    """Write back every saved file that is no longer there. Returns (restored, lost): the paths put back, and the
    unsaved paths that are gone, which could not be."""
    restored = []
    for path, content in backup.saved.items():
        target = backup.root / path
        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        restored.append(path)
    lost = [path for path in backup.unsaved if not (backup.root / path).exists()]
    return sorted(restored), sorted(lost)


def restore_changed(backup):
    """Write back every saved file whose bytes differ from the saved bytes, or that is gone. Returns (restored,
    unguarded): the paths put back, and the unsaved paths, whose bytes could not be checked."""
    restored = []
    for path, content in backup.saved.items():
        target = backup.root / path
        if target.is_file() and target.read_bytes() == content:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        restored.append(path)
    return sorted(restored), sorted(backup.unsaved)
