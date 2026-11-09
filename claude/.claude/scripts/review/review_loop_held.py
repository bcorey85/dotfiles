"""review_loop_held.py: the files another session holds in a shared tree. When the caller scopes a run to its own
files, every other dirty file is held. The loop never reviews a held file, sends no item on one to a coder, and tells
each fix coder never to edit one. It never writes a held file back: a held file that changed during a coder call is
left as it is and noted."""
import pathlib

import review_loop_plan
import worktree_snapshot

HELD_FILE_REASON = "the file is held by another session"
# One note per coder call that ran while held files changed, for the packet's tool_fault. An item on a held file is
# no fault: skip_held_items records it in skipped_fp.
HELD_FAULTS = []


def run_held_files(repo, only_files):
    """The held files of a run: when the caller scoped the run to `only_files`, every other file dirty now."""
    if not only_files:
        return set()
    dirty = review_loop_plan.scope(repo)
    return set(dirty) - set(only_files)


def held_path_in_repo(path, repo):
    """`path` relative to `repo` when it is absolute and sits under it, else unchanged."""
    if not path or not pathlib.PurePath(path).is_absolute():
        return path
    try:
        return pathlib.PurePath(path).relative_to(repo).as_posix()
    except ValueError:
        return path


def names_held_file(path, held_path):
    """True when `path` is `held_path` or a tail of it. A held file is never matched by a longer path: a finding at
    `sub/notes.py` is not on a held root `notes.py`."""
    if not path:
        return False
    return path == held_path or held_path.endswith("/" + path)


def tail_names_held_file(path, held, owned):
    """True when the tail `path` names exactly one held file and no file the run owns."""
    held_matches = [held_path for held_path in held if names_held_file(path, held_path)]
    owned_matches = [owned_path for owned_path in owned if names_held_file(path, owned_path)]
    return len(held_matches) == 1 and not owned_matches


def split_held_findings(items, held, owned, repo):
    """(the findings or nits that name no held file, the ones that do). `owned` is the run's own files. Records
    nothing."""
    kept, held_items = [], []
    for item in items:
        # A reviewer may name the file by absolute path or by a tail of it.
        path = held_path_in_repo(item.path, repo)
        # A path that is a file in the repo is exact: only an equal held path holds it, never a longer one.
        exact = bool(path) and (pathlib.Path(repo) / path).is_file()
        is_held = path in held if exact else tail_names_held_file(path, held, owned)
        if is_held:
            held_items.append(item)
        else:
            kept.append(item)
    return kept, held_items


def skip_held_items(items, held, owned, skipped_fp, repo):
    """(the items that name no held file, the held items, the number of held items newly recorded). Each held item
    goes into `skipped_fp` once with HELD_FILE_REASON, however many callers or rounds meet it."""
    kept, held_items = split_held_findings(items, held, owned, repo)
    recorded = 0
    for item in held_items:
        if any(entry["item"] == item and entry["reason"] == HELD_FILE_REASON for entry in skipped_fp):
            continue
        skipped_fp.append({"item": item, "reason": HELD_FILE_REASON})
        recorded += 1
    return kept, held_items, recorded


def digests(repo, held):
    """{path: digest} of each held file, taken before a coder call."""
    root = pathlib.Path(repo)
    return {path: worktree_snapshot.file_hash(root, path) for path in held}


def note_changed(role, repo, before):
    """Note in HELD_FAULTS each held file whose bytes differ from `before`. The file is left as it is: its owner may
    have written it during the call."""
    root = pathlib.Path(repo)
    changed = sorted(path for path, digest in before.items() if worktree_snapshot.file_hash(root, path) != digest)
    if changed:
        HELD_FAULTS.append(f"held files changed while {role} ran (by the coder or by the session that holds them); "
                           "the loop left them as they are, so check them: " + ", ".join(changed))
