"""approval_asks_store.py: the file of unsettled approval-only paths in the review-fix folder (`APPROVAL_ASKS_NAME`):
each path mapped to the blob id its edit is measured against (None when the file was absent, `UNKNOWN_BASE` when the
pre-pass content is not known), and the wanted-change asks ({text, change, path, line, title}: a finding's change
on an approval-only file). The review loop writes it, a resumed loop
reads it, and a ruling on an approval ask (see `is_approval_ask`), accepted or rejected, removes its path or its
wanted-change entry."""
import json

import script_utils
from ask_outcome_words import USER_ONLY_KEY
from review_fix_names import APPROVAL_ASKS_NAME, HELD_APPROVAL_NAME, REVIEW_FIX_FOLDER

# The saved base of a path whose pre-pass content is not known (the snapshot could not list the files, or could not
# hash this one). A blob id is hex, so it never equals this word; None stays the base of an absent file.
UNKNOWN_BASE = "unknown"

CHANGE_PREFIX = "revert the fix coder's edit to `"
CHANGE_SUFFIX = "`."
WANTED_TARGET_PREFIX = "(edit to `"
WANTED_TARGET_SUFFIX = "`)"


def approval_change(path):
    """The change the approval ask proposes for `path`. An accepted ask with a known base (a saved absent
    base for a file HEAD tracks counts as unknown) is restored and left out of the next fix run; an accepted ask
    with an unknown base reaches it as
    `<file_line> [<class>] Proposed change: <change>`, so the change is the part that names the ask there."""
    return f"{CHANGE_PREFIX}{path}{CHANGE_SUFFIX}"


def approval_path_of_change(change):
    """The path an approval ask's change text names, or None when the text is not an approval change."""
    if not isinstance(change, str):
        return None
    if not (change.startswith(CHANGE_PREFIX) and change.endswith(CHANGE_SUFFIX)):
        return None
    return change[len(CHANGE_PREFIX):-len(CHANGE_SUFFIX)]


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


PATHS_KEY = "paths"
WANTED_KEY = "wanted"
WANTED_FIELDS = {"text": str, "change": str, "path": str, "line": int, "title": str}
WANTED_SHAPE = "{" + ", ".join(WANTED_FIELDS) + "}"


def wanted_edit_target(path):
    """The words a wanted-change ask's change ends with to name the file exactly. An accepted ask reaches the next
    run as a finding whose location is empty (UNLOCATED) for a path whose folder holds a space, so the run reads
    the path from these words."""
    return f"{WANTED_TARGET_PREFIX}{path}{WANTED_TARGET_SUFFIX}"


def wanted_path_of_change(change):
    """The path a wanted-change ask's change ends with (see `wanted_edit_target`), or None when it does not end with
    that form, is not a string, or names an empty path."""
    if not isinstance(change, str):
        return None
    if not change.endswith(WANTED_TARGET_SUFFIX):
        return None
    start = change.rfind(WANTED_TARGET_PREFIX)
    if start < 0:
        return None
    path = change[start + len(WANTED_TARGET_PREFIX):-len(WANTED_TARGET_SUFFIX)]
    if not path:
        return None
    return path


def wanted_entry(text, change, path, line, title):
    """One saved wanted-change ask, in the shape `is_wanted_entry` checks."""
    values = {"text": text, "change": change, "path": path, "line": line, "title": title}
    return {name: values[name] for name in WANTED_FIELDS}


def is_wanted_entry(entry):
    if not isinstance(entry, dict):
        return False
    return all(isinstance(entry.get(name), kind) for name, kind in WANTED_FIELDS.items())


def read_saved_asks(repo):
    """The saved asks of `repo` as (paths, wanted): `paths` maps each approval-only path to the blob id its edit is
    measured against (None when the file was absent, `UNKNOWN_BASE` when the pre-pass content is not known);
    `wanted` is a list of {text, change, path, line, title} for the wanted-change asks (each is a finding's change;
    `path` is the exact repo-relative path and `title` the finding's title). Both are empty when nothing was saved.
    The file holds {"paths": ..., "wanted": [...]}; an older file that is a flat object of path to blob id reads as
    paths only. Raises ApprovalAsksFileError naming the file when it is damaged: a damaged file stops the run
    rather than losing an ask."""
    saved = approval_paths_file(repo)
    if saved is None or not saved.exists():
        return {}, []
    try:
        contents = json.loads(saved.read_text())
    except ValueError as error:
        raise ApprovalAsksFileError(
            f"{saved} is not readable JSON ({error}); delete it or fix it to a JSON object with `paths` (path to "
            f"blob id) and `wanted` (a list of {WANTED_SHAPE})"
        ) from error
    if isinstance(contents, dict) and PATHS_KEY in contents:
        paths, wanted = contents[PATHS_KEY], contents.get(WANTED_KEY, [])
    else:
        paths, wanted = contents, []
    paths_ok = isinstance(paths, dict) and all(isinstance(base, (str, type(None))) for base in paths.values())
    wanted_ok = isinstance(wanted, list) and all(is_wanted_entry(entry) for entry in wanted)
    if not (paths_ok and wanted_ok):
        raise ApprovalAsksFileError(
            f"{saved} must hold a JSON object with `paths` (path to blob id) and `wanted` (a list of "
            f"{WANTED_SHAPE}); delete it or fix it")
    return paths, wanted


def read_approval_paths(repo):
    """The saved approval-only paths of `repo`, each mapped to the blob id its edit is measured against; {} when none
    were saved. Raises ApprovalAsksFileError when the file is damaged (see `read_saved_asks`)."""
    return read_saved_asks(repo)[0]


def write_saved_asks(repo, paths, wanted):
    """Saves `paths` (path to base blob id, None for an absent file, or `UNKNOWN_BASE`) and `wanted` (the
    wanted-change entries, shaped as `read_saved_asks` describes), the asks of `repo` still waiting on the user, for a
    resumed run to read."""
    saved = approval_paths_file(repo)
    if saved is None:
        return
    saved.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(saved, json.dumps({PATHS_KEY: paths, WANTED_KEY: wanted}))


def user_only_changes(asks):
    """The change text of each ask in `asks` that is user-only."""
    return [item.get("change") for item in asks if item.get(USER_ONLY_KEY)]


def is_approval_ask(item):
    """True when the ask `item` is an approval ask: marked user-only, or its change reverts a coder's edit to an
    approval-only file or ends with a wanted-change target. A session rules the scripts CLAUDE.md's asks, so those
    carry no user-only mark and still leave the saved paths when ruled."""
    if item.get(USER_ONLY_KEY):
        return True
    change = item.get("change")
    if approval_path_of_change(change) is not None:
        return True
    return wanted_path_of_change(change) is not None


def approval_ask_changes(asks):
    """The change text of each approval ask in `asks` (see `is_approval_ask`)."""
    return [item.get("change") for item in asks if is_approval_ask(item)]


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
    """Raises ApprovalAsksFileError when the saved approval paths or the held changes file is damaged and an approval
    ask in `asks` would need it. Call it before a ruling writes anything, so a damaged file stops the ruling with
    nothing written."""
    if not approval_ask_changes(asks):
        return
    read_approval_paths(repo)
    read_held_changes(repo)


def forget_ruled_approval_paths(repo, asks):
    """Drops from the saved approval paths of `repo` each path whose approval ask (see `is_approval_ask`) is in
    `asks`, ruled with any outcome, so a resumed run never files it again. Leaves the file alone when no saved path
    is ruled."""
    ruled_changes = approval_ask_changes(asks)
    if not ruled_changes:
        return
    forget_held_changes(repo, ruled_changes)
    saved, wanted = read_saved_asks(repo)
    # Matched on the change text, which is written from the exact filed path: parsing the path back out of the ask's
    # location drops a folder name that holds a space.
    kept = {path: base for path, base in saved.items() if approval_change(path) not in ruled_changes}
    kept_wanted = [entry for entry in wanted if entry["change"] not in ruled_changes]
    if len(kept) != len(saved) or len(kept_wanted) != len(wanted):
        write_saved_asks(repo, kept, kept_wanted)
