"""approval_asks_store.py: the file of unsettled approval-only paths in the review-fix folder (`APPROVAL_ASKS_NAME`):
each path mapped to the blob id its edit is measured against. The review loop writes it, a resumed loop reads it, and
a ruling on a user-only approval ask, accepted or rejected, removes its path."""
import json

import script_utils
from ask_outcome_words import USER_ONLY_KEY
from review_fix_names import APPROVAL_ASKS_NAME, HELD_APPROVAL_NAME, REVIEW_FIX_FOLDER


def approval_change(path):
    """The change the approval ask proposes for `path`. An accepted ask reaches the next fix run as
    `<file_line> [<class>] Proposed change: <change>`, so the change is the part that names the ask there."""
    return f"revert the fix coder's edit to `{path}`."


def review_fix_file(repo, name):
    """The file `name` in the review-fix folder of `repo`'s git dir, or None when git names no git dir for `repo`
    (nothing to resume from). The files sit in the repo they answer, not the repo of the session that saved the fix
    state."""
    folder = script_utils.git_path(repo, REVIEW_FIX_FOLDER)
    if folder is None:
        return None
    return folder / name


def approval_paths_file(repo):
    """The file of the unsettled approval-only paths in the review-fix folder of `repo`'s git dir, or None."""
    return review_fix_file(repo, APPROVAL_ASKS_NAME)


class ApprovalAsksFileError(Exception):
    """The saved approval-paths file is damaged."""


def read_approval_paths(repo):
    """The saved approval-only paths of `repo`, each mapped to the blob id its edit is measured against (None when the
    file was absent); {} when none were saved. Raises ApprovalAsksFileError naming the file when it is not a JSON
    object of path to blob id: a damaged file stops the run rather than losing an ask."""
    saved = approval_paths_file(repo)
    if saved is None or not saved.exists():
        return {}
    try:
        paths = json.loads(saved.read_text())
    except ValueError as error:
        raise ApprovalAsksFileError(
            f"{saved} is not readable JSON ({error}); delete it or fix it to a JSON object of path to blob id"
        ) from error
    if not isinstance(paths, dict) or not all(isinstance(base, (str, type(None))) for base in paths.values()):
        raise ApprovalAsksFileError(f"{saved} must hold a JSON object of path to blob id; delete it or fix it")
    return paths


def write_approval_paths(repo, paths):
    """Saves `paths` (path to base blob id), the approval-only paths of `repo` still asked about, for a resumed run to
    read."""
    saved = approval_paths_file(repo)
    if saved is None:
        return
    saved.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(saved, json.dumps(paths))


def user_only_changes(asks):
    """The change text of each ask in `asks` that is user-only."""
    return [item.get("change") for item in asks if item.get(USER_ONLY_KEY)]


def held_changes_file(repo):
    """The file of the approval changes that kept (held) packets wait on, in the review-fix folder of `repo`'s git
    dir, or None when git names no git dir for `repo`. It sits with the packet rows."""
    return review_fix_file(repo, HELD_APPROVAL_NAME)


def read_held_changes(repo):
    """The approval changes a kept packet of `repo` holds for the user: a later loop run leaves the path of each out
    of its own asks, as the kept packet already waits on the user for it. Empty when none are saved. A damaged file
    raises ApprovalAsksFileError."""
    saved = held_changes_file(repo)
    if saved is None or not saved.exists():
        return set()
    try:
        changes = json.loads(saved.read_text())
    except ValueError as error:
        raise ApprovalAsksFileError(
            f"{saved} is not readable JSON ({error}); delete it or fix it to a JSON list of change texts"
        ) from error
    if not isinstance(changes, list) or not all(isinstance(change, str) for change in changes):
        raise ApprovalAsksFileError(f"{saved} must hold a JSON list of change texts; delete it or fix it")
    return set(changes)


def write_held_changes(repo, changes):
    """Adds `changes` to the approval changes that kept packets of `repo` hold for the user."""
    saved = held_changes_file(repo)
    if saved is None or not changes:
        return
    held = read_held_changes(repo) | set(changes)
    saved.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(saved, json.dumps(sorted(held)))


def forget_held_changes(repo, changes):
    """Drops `changes` from the held approval changes of `repo`, as the user ruled the kept packet that held them.
    Leaves the file alone when none of them is held."""
    held = read_held_changes(repo)
    kept = held - set(changes)
    if kept == held:
        return
    saved = held_changes_file(repo)
    script_utils.write_text_atomically(saved, json.dumps(sorted(kept)))


def check_approval_paths_readable(repo, asks):
    """Raises ApprovalAsksFileError when the saved approval paths or the held changes file is damaged and a user-only
    ask in `asks` would need it. Call it before a ruling writes anything, so a damaged file stops the ruling with
    nothing written."""
    if not user_only_changes(asks):
        return
    read_approval_paths(repo)
    read_held_changes(repo)


def forget_ruled_approval_paths(repo, asks):
    """Drops from the saved approval paths of `repo` each path whose user-only approval ask is in `asks`, ruled with
    any outcome, so a resumed run never files it again. Leaves the file alone when no saved path is ruled."""
    ruled_changes = user_only_changes(asks)
    if not ruled_changes:
        return
    forget_held_changes(repo, ruled_changes)
    saved = read_approval_paths(repo)
    # Matched on the change text, which is written from the exact filed path: parsing the path back out of the ask's
    # location drops a folder name that holds a space.
    kept = {path: base for path, base in saved.items() if approval_change(path) not in ruled_changes}
    if len(kept) != len(saved):
        write_approval_paths(repo, kept)
