"""approval_asks_store.py: the file of unsettled approval-only paths in the review-fix folder (`APPROVAL_ASKS_NAME`):
each path mapped to the blob id its edit is measured against. The review loop writes it, a resumed loop reads it, and
a ruling on a user-only approval ask, accepted or rejected, removes its path."""
import json

import script_utils
from ask_outcome_words import USER_ONLY_KEY
from review_fix_names import APPROVAL_ASKS_NAME, REVIEW_FIX_FOLDER


def approval_change(path):
    """The change the approval ask proposes for `path`. An accepted ask reaches the next fix run as
    `<file_line> [<class>] Proposed change: <change>`, so the change is the part that names the ask there."""
    return f"revert the fix coder's edit to `{path}`."


def approval_paths_file(repo):
    """The file of the unsettled approval-only paths in the review-fix folder of `repo`'s git dir, or None when git
    names no git dir for `repo` (nothing to resume from)."""
    folder = script_utils.git_path(repo, REVIEW_FIX_FOLDER)
    if folder is None:
        return None
    return folder / APPROVAL_ASKS_NAME


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


def check_approval_paths_readable(repo, asks):
    """Raises ApprovalAsksFileError when the saved file is damaged and a user-only ask in `asks` would need it. Call it
    before a ruling writes anything, so a damaged file stops the ruling with nothing written."""
    if user_only_changes(asks):
        read_approval_paths(repo)


def forget_ruled_approval_paths(repo, asks):
    """Drops from the saved approval paths of `repo` each path whose user-only approval ask is in `asks`, ruled with
    any outcome, so a resumed run never files it again. Leaves the file alone when no saved path is ruled."""
    ruled_changes = user_only_changes(asks)
    if not ruled_changes:
        return
    saved = read_approval_paths(repo)
    # Matched on the change text, which is written from the exact filed path: parsing the path back out of the ask's
    # location drops a folder name that holds a space.
    kept = {path: base for path, base in saved.items() if approval_change(path) not in ruled_changes}
    if len(kept) != len(saved):
        write_approval_paths(repo, kept)
