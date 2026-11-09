"""review_loop_held.py: the files another session holds in a shared tree. A held file was dirty when the run started
and is not one of the run's own files. The loop never reviews one, tells each fix coder never to edit one, and puts
back the bytes of any held file a fix coder changed anyway."""
import file_backup
import review_loop_plan

# A held file larger than this is not saved, so a coder's edit to it is reported but cannot be undone.
MAX_HELD_FILE_BYTES = 16 * 1024 * 1024
MAX_HELD_TOTAL_BYTES = 256 * 1024 * 1024
# One note per fix call that changed a held file, for the packet's tool_fault.
HELD_FAULTS = []


def run_held_files(repo, named_held, only_files):
    """The held files of a run: the ones the caller names, plus, when the caller scoped the run to `only_files`, every
    other file dirty now."""
    held = set(named_held)
    if only_files:
        dirty = review_loop_plan.scope(repo)
        held |= set(dirty) - set(only_files)
    return held


def without_held(files, held):
    """`files` (a {path: entry} mapping or a list of paths) with the held paths left out, in the same shape."""
    if isinstance(files, dict):
        return {path: entry for path, entry in files.items() if path not in held}
    return [path for path in files if path not in held]


def save(repo, held):
    """The bytes of each held file, to put back after a coder call."""
    return file_backup.save_files(repo, held, max_file_bytes=MAX_HELD_FILE_BYTES, max_total_bytes=MAX_HELD_TOTAL_BYTES)


def restore_held(role, backup):
    """Write back every held file the call changed or deleted, and note each in HELD_FAULTS. Returns the paths put
    back."""
    restored, unguarded = file_backup.restore_changed(backup)
    if restored:
        HELD_FAULTS.append(f"{role} edited files another session holds; the loop put back their bytes: "
                           + ", ".join(restored))
    if unguarded:
        HELD_FAULTS.append(f"{role} ran beside held files too large to save, so an edit to them was not undone: "
                           + ", ".join(unguarded))
    return restored
