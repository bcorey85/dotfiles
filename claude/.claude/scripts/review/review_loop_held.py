"""review_loop_held.py: the files another session holds in a shared tree. A held file was dirty when the run started
and is not one of the run's own files. The loop never reviews one, tells each fix coder never to edit one, and undoes
the coder's own writes to one when no other change landed on it during the call."""
import file_backup
import review_loop_plan
import session_edits

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


def coder_result(saved, writes):
    """The bytes a held file holds when only the coder's recorded writes landed on its saved bytes; None when they
    cannot be replayed."""
    try:
        text = saved.decode()
        return session_edits.replayed_text(text, writes).encode()
    except (UnicodeDecodeError, session_edits.ReplayError):
        return None


def restore_held(role, backup, session_id):
    """Undo the coder's own writes to held files. A held file goes back to its bytes from before the call only when
    it holds exactly the coder's result, so an edit the owning session made during the call is never erased. A held
    file the coder wrote that holds anything else is left as it is, and noted in HELD_FAULTS. Returns the paths put
    back."""
    if backup.unsaved:
        HELD_FAULTS.append(f"{role} ran beside held files too large to save, so an edit to them was not undone: "
                           + ", ".join(backup.unsaved))
    changed = {}
    for path, saved in backup.saved.items():
        target = backup.root / path
        now = target.read_bytes() if target.is_file() else None
        if now != saved:
            changed[path] = (saved, now)
    if not changed:
        return []

    transcript = session_edits.session_transcript(session_id)
    if transcript is None:
        HELD_FAULTS.append(f"{role} ran while held files changed, and its transcript is not there to show whose "
                           f"change it was, so the loop left them as they are: {', '.join(sorted(changed))}")
        return []

    writes = session_edits.file_writes(transcript, backup.root)
    restored = []
    left = []
    for path, (saved, now) in sorted(changed.items()):
        if path not in writes:
            continue
        if coder_result(saved, writes[path]) != now:
            left.append(path)
            continue
        (backup.root / path).write_bytes(saved)
        restored.append(path)

    if restored:
        HELD_FAULTS.append(f"{role} edited files another session holds; the loop put back their bytes: "
                           + ", ".join(restored))
    if left:
        HELD_FAULTS.append(f"{role} edited files another session holds, and they changed again during the call, so "
                           "the loop left them as they are: " + ", ".join(left))
    return restored
