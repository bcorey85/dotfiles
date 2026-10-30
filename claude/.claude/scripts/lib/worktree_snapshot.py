"""The working-tree state of a git repo before and after a command, and the report of what the command changed: a
tracked file it rewrote and a file it created are named, and both stay as they are. Any repo, any command."""
import hashlib
import pathlib

from numstat import changed_lines_by_path
from script_utils import git_output, repo_root

UNTRACKED = "??"
# The hash of a file that exists but cannot be read.
UNREADABLE = "unreadable"
# A rename or copy entry in `git status --porcelain -z`, in the index column or the work tree column, is followed by a
# second entry that holds the old path.
RENAME_CODES = ("R", "C")
# How many paths one `git hash-object` call gets, so a big dirty tree stays under the OS argument limit.
HASH_CHUNK_SIZE = 1000
# The three lists changes_since returns, in order.
CHANGE_KINDS = ("changed", "rewrote_edited", "created")


def status_entries(root):
    """({path: two-letter status}, {new path: old path} of each rename or copy) of every dirty or untracked file,
    paths relative to the work tree root."""
    output = git_output(root, "status", "--porcelain", "-z", "--find-renames",
                         "--untracked-files=all") or ""
    entries = output.split("\0")
    codes = {}
    origins = {}
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue

        code, path = entry[:2], entry[3:]
        codes[path] = code
        if code[0] in RENAME_CODES or code[1] in RENAME_CODES:
            origins[path] = entries[index]
            index += 1
    return codes, origins


def status_codes(root):
    """{path: two-letter status} of every dirty or untracked file, paths relative to the work tree root."""
    return status_entries(root)[0]


def staged_paths(root):
    """The paths the index holds changes for: the index status column is neither blank nor untracked."""
    return [name for name, code in status_codes(root).items() if code[0] not in " ?"]


def file_hash(root, path):
    """The SHA-256 of the file's bytes, None when it does not exist, or UNREADABLE when it cannot be read."""
    target = root / path
    if not target.is_file():
        return None

    try:
        with target.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError:
        return UNREADABLE


def working_tree_changes(root):
    """{path: {"code", "hash", "added", "deleted", "new"}} of every dirty or untracked file against HEAD, from one scan.

    code is the two-letter status. hash is the git blob hash of the content the path reads now (what
    `git hash-object <path>` prints): a symlink to a file hashes as that file's bytes, not as the link text. It is None
    when nothing readable as a file is there: the path is gone, is a folder, or is a symlink to nothing. added and
    deleted are git's numstat counts for a tracked file (0 for a binary one) and, for an untracked file, its whole
    line count as bytes.splitlines counts it (\\n, \\r and \\r\\n each end a line). new is True for an untracked file
    and one added to the index, intent-to-add included. A renamed file is listed under its new path only, with just
    the lines the rename edited: a pure rename adds none."""
    root = pathlib.Path(root)
    codes = status_codes(root)
    counts = changed_lines_by_path(git_output(root, "diff", "--numstat", "-z", "--find-renames", "HEAD") or "")
    existing = [path for path in codes if (root / path).is_file()]

    # An untracked file that cannot be read stops the scan with the OS error.
    for path in existing:
        if codes[path] == UNTRACKED:
            counts[path] = (len((root / path).read_bytes().splitlines()), 0)

    printed_lines = []
    for start in range(0, len(existing), HASH_CHUNK_SIZE):
        printed = git_output(root, "hash-object", "--", *existing[start:start + HASH_CHUNK_SIZE])
        if printed is None:
            raise RuntimeError(f"`git hash-object` failed in {root} for the dirty files")

        printed_lines.extend(printed.splitlines())

    blob_hashes = dict(zip(existing, printed_lines, strict=True))
    changes = {}
    for path, code in codes.items():
        added, deleted = counts.get(path, (0, 0))
        is_new = code == UNTRACKED or "A" in code
        changes[path] = {"code": code, "hash": blob_hashes.get(path), "added": added, "deleted": deleted,
                         "new": is_new}
    return changes


def take(repo):
    """The state to compare against later: the work tree root, every dirty file's status, and a hash of each dirty
    file, tracked or untracked. None when the repo is not in a git work tree."""
    root = repo_root(repo)
    if root is None:
        return None

    codes = status_codes(root)
    dirty_hashes = {path: file_hash(root, path) for path in codes}
    return {"root": root, "codes": codes, "hashes": dirty_hashes}


def changes_since(before):
    """What a command changed since `before` (from take), as (changed, rewrote_edited, created) paths; nothing is
    undone. A tracked file that was clean and is modified now is changed. A tracked file that was dirty before (it
    holds someone's edits) and now holds other bytes, or is back to the index, is rewrote_edited, and so is an
    untracked file that was there before and now holds other bytes. An untracked file that was not there is created.
    All three lists are sorted and empty for a `before` of None."""
    if before is None:
        return [], [], []

    root = before["root"]
    after = status_codes(root)
    changed = []
    for path, code in after.items():
        is_clean_before = path not in before["codes"]
        is_worktree_change = code != UNTRACKED and code[1] != " "
        if is_clean_before and is_worktree_change:
            changed.append(path)

    rewrote_edited = [path for path, saved_hash in before["hashes"].items() if file_hash(root, path) != saved_hash]
    created = [path for path, code in after.items() if code == UNTRACKED and path not in before["codes"]]
    return sorted(changed), sorted(rewrote_edited), sorted(created)
