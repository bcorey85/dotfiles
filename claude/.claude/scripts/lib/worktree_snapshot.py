"""The working-tree state of a git repo before and after a command, and the report of what the command changed: a
tracked file it rewrote and a file it created are named, and both stay as they are. Any repo, any command."""
import hashlib

from script_utils import git_output, repo_root

UNTRACKED = "??"
# The hash of a file that exists but cannot be read.
UNREADABLE = "unreadable"
# A rename or copy entry in `git status --porcelain -z` is followed by a second entry that holds the old path.
RENAME_CODES = ("R", "C")
# The three lists changes_since returns, in order.
CHANGE_KINDS = ("changed", "rewrote_edited", "created")


def status_codes(root):
    """{path: two-letter status} of every dirty or untracked file, paths relative to the work tree root."""
    output = git_output(root, "status", "--porcelain", "-z", "--untracked-files=all") or ""
    entries = output.split("\0")
    codes = {}
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue

        code, path = entry[:2], entry[3:]
        codes[path] = code
        if code[0] in RENAME_CODES:
            index += 1
    return codes


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
