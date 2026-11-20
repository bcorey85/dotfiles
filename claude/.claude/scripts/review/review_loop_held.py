"""review_loop_held.py: the files another session holds in a shared tree. When the caller scopes a run to its own
files, every other dirty file is held. The loop never reviews a held file and tells each fix coder never to edit a
held file whose holder row names a session. It sends no item on such a file to a coder; the item comes back unfixed
in held_unfixed with that proof. An item on a held file with no holder row goes to the coder like any other. It never
writes a held file back: a held file that changed during a coder call is left as it is and noted."""
import pathlib

import review_loop_plan
import session_registry
import worktree_snapshot
from review_loop_prompt_file import holder_row

# One note per coder call that ran while held files changed, for the packet's tool_fault. An item on a held file is
# no fault: skip_held_items records it in held_unfixed.
HELD_FAULTS = []


def run_held_files(repo, caller_held, only_files):
    """The held files of a run: the files the caller names as held, plus, when the caller scoped the run to
    `only_files`, every other file dirty now."""
    held = set(caller_held)
    if not only_files:
        return held
    dirty = review_loop_plan.scope(repo)
    return held | (set(dirty) - set(only_files))


def implicit_holders(repo, held_files, known_holders, only_files, own_session_id):
    """{path: holder row} for the files held only because the run is scoped to `only_files` (dirty, outside the
    scope, with no row yet in `known_holders`), when a live session other than this run's works inside the repo.
    With no such session they are the run's own leftovers and are not held by anyone."""
    if not only_files:
        return {}
    implicit = sorted(path for path in held_files if path not in known_holders)
    if not implicit:
        return {}
    holder = session_registry.other_live_session_in(repo, own_session_id)
    if holder is None:
        return {}
    session = session_registry.holder_label(holder)
    claim = "dirty, outside the run's --file scope"
    return {path: holder_row(path, session, claim) for path in implicit}


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


def held_path_of(item, held, owned, repo):
    """The held file a finding or nit names, None when it names none. `owned` is the run's own files."""
    # A reviewer may name the file by absolute path or by a tail of it.
    path = held_path_in_repo(item.path, repo)
    # A path that is a file in the repo is exact: only an equal held path holds it, never a longer one.
    exact = bool(path) and (pathlib.Path(repo) / path).is_file()
    if exact:
        return path if path in held else None
    if not tail_names_held_file(path, held, owned):
        return None
    return next(held_path for held_path in sorted(held) if names_held_file(path, held_path))


def split_held_findings(items, held, owned, repo):
    """(the findings or nits that name no held file, the ones that do). `owned` is the run's own files. Records
    nothing."""
    kept, held_items = [], []
    for item in items:
        if held_path_of(item, held, owned, repo) is None:
            kept.append(item)
        else:
            held_items.append(item)
    return kept, held_items


def caller_holders(caller_held, held_by):
    """{path: holder row} for the files the caller names as held: the held-by row where the caller gave one, else a
    row naming the caller. The rows of held-by for other paths are kept too."""
    holders = dict(held_by)
    for path in caller_held:
        holders.setdefault(path, holder_row(path, "the caller", "named held by the caller"))
    return holders


def held_reason(holder):
    return f"held by {holder['session']}: {holder['claim']}"


def skip_held_items(items, held, owned, held_unfixed, repo, holders):
    """(the items the coder may get, the held items). An item on a held file whose holder row names a session goes
    into `held_unfixed` once with the reason `held by <session>: <claim>`,
    however many callers or rounds meet it. An item on a held file with no holder row is no proof of a holder: it
    stays with the items the coder gets."""
    kept, held_items = [], []
    for item in items:
        held_path = held_path_of(item, held, owned, repo)
        holder = holders.get(held_path) if held_path is not None else None
        if holder is None:
            kept.append(item)
            continue
        held_items.append(item)
        reason = held_reason(holder)
        if any(entry["item"] == item and entry["reason"] == reason for entry in held_unfixed):
            continue
        held_unfixed.append({"item": item, "reason": reason})
    return kept, held_items


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
