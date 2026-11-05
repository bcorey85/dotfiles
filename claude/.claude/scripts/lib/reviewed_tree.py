"""The working tree a session's converged review covered, kept per repo so a later commit of that same tree passes.

A review-loop records its tree when it ends clean: the scripted loop at its hand-back
(review_loop_packet.write_handback_rows). Then
review_commit_gate.py reads it back at commit time. A tree is its fingerprint, `tree_fingerprint`: "sha256:" and the
hash of `git diff --binary <base> -- .` (git's raw output bytes, never decoded) followed by, for each untracked,
non-ignored file in name order, `\0untracked\0<name>\0<git hash-object>`. The reviewed tree leaves the repo's notes
paths (notes_paths.py) out of both parts, so an edit of a plan or note after the review keeps the credit and any
other edit voids it.
Verify stores the `tree_fingerprint` whole-tree value (its context and ledger review rows), not the reviewed value,
with an optional path left out of both parts. The
bytes match what verify stored for any tree whose diff is valid UTF-8; a diff with other bytes in a tracked text edit
hashes differently from before, so verify-prep and the branch review rerun once there.

State: ~/.claude/state/review-gate/<session>.reviewed, one JSON object of repo top level -> fingerprint, and
~/.claude/state/review-gate/reviewed-trees.json, repo top level -> the latest fingerprints any session recorded. A value
written in an older form never equals a current one, so the tree counts as not reviewed until it is recorded again.
"""
import hashlib
import json
import os
import pathlib
import sys

import notes_paths
import script_utils

GIT_TIMEOUT_SECONDS = 10
REVIEWED_SUFFIX = ".reviewed"
# The reviewed trees of every session, so a commit from a fork's parent, a resumed session or a session after /clear
# earns the credit of a review that converged under another session id. It credits only the exact tree reviewed.
SHARED_REVIEWED_NAME = "reviewed-trees.json"
SHARED_LIMIT = 50


class TreeFingerprintError(Exception):
    """git failed, or the tree holds a file name that cannot be fingerprinted."""


def review_gate_dir():
    return pathlib.Path.home() / ".claude" / "state" / "review-gate"


def reviewed_file(session):
    return review_gate_dir() / (session + REVIEWED_SUFFIX)


def shared_reviewed_file():
    return review_gate_dir() / SHARED_REVIEWED_NAME


def tree_fingerprint(top, base="HEAD", exclude_rel=None, error_type=TreeFingerprintError, timeout=None,
                     notes_entries=None):
    """Content fingerprint of the working tree at `top` as it stands: `git diff <base>` plus the hash of each
    untracked file, as "sha256:<hex>".

    Equal fingerprints mean equal content, whatever the commits, mtimes or renames in between. `exclude_rel` (a path
    relative to the top level) leaves a file or directory out of both parts. `notes_entries`, a list of
    `.claude/notes-paths` entries, leaves every notes path they and docs/ name out of both parts; None leaves them
    in. Each git call may run `timeout` seconds (None: no limit). Raises error_type when git fails or runs past it,
    or an untracked file name holds a newline."""
    def git(argv, stdin=None):
        return script_utils.run_or_raise(["git", *argv], error_type, cwd=top, check=True, stdin=stdin,
                                         timeout=timeout, as_bytes=True)

    digest = hashlib.sha256()
    diff_argv = ["diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", base, "--", "."]
    if exclude_rel:
        diff_argv.append(f":(exclude,literal){exclude_rel}")
    if notes_entries is not None:
        diff_argv += notes_paths.exclude_pathspecs(notes_entries)
    digest.update(git(diff_argv).stdout)

    listing = git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout

    def is_excluded(name):
        path = os.fsdecode(name)
        if exclude_rel and script_utils.path_is_under(path, exclude_rel):
            return True
        return notes_entries is not None and notes_paths.is_notes_path(path, notes_entries)

    names = sorted(name for name in listing.split(b"\0") if name and not is_excluded(name))
    if any(b"\n" in name for name in names):
        raise error_type("an untracked file name holds a newline; rename it so the tree can be fingerprinted")

    if names:
        paths_input = b"\n".join(names) + b"\n"
        hashed = git(["hash-object", "--stdin-paths"], stdin=paths_input)
        file_hashes = hashed.stdout.split()
        if len(file_hashes) != len(names):
            raise error_type(f"git hash-object returned {len(file_hashes)} hashes for {len(names)} untracked files")
        for name, file_hash in zip(names, file_hashes, strict=True):
            digest.update(b"\0untracked\0" + name + b"\0" + file_hash)
    return "sha256:" + digest.hexdigest()


def fingerprint_base(top, timeout=None):
    """(head, base) for fingerprinting the work tree at `top`: HEAD's commit as both, or "unborn" and the empty tree
    for a repo with no commit yet. A failed HEAD lookup counts as no commit; None only when git cannot name the
    empty tree."""
    head = script_utils.git_output(top, "rev-parse", "--verify", "-q", "HEAD", timeout=timeout)
    if head is not None:
        return head, head

    empty_tree = script_utils.git_output(top, "hash-object", "-t", "tree", os.devnull, timeout=timeout)
    if empty_tree is None:
        return None
    return "unborn", empty_tree


def work_tree_fingerprint(repo, log=None):
    """The fingerprint of the work tree that holds `repo` as it stands, against `fingerprint_base`, with the file `log`
    left out when it lies inside the tree; None when `repo` is in no work tree. Raises TreeFingerprintError when git
    cannot name the base tree or cannot fingerprint the tree."""
    top = script_utils.repo_root(repo, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    top = top.resolve()
    exclude_rel = None
    if log:
        log_path = pathlib.Path(log).resolve()
        exclude_rel = log_path.relative_to(top).as_posix() if log_path.is_relative_to(top) else None

    found = fingerprint_base(top, timeout=GIT_TIMEOUT_SECONDS)
    if found is None:
        raise TreeFingerprintError("git could not name the base tree")

    _, base = found
    return tree_fingerprint(top, base=base, exclude_rel=exclude_rel, timeout=GIT_TIMEOUT_SECONDS)


def fingerprint(repo_dir):
    """(repo top level, whole-tree fingerprint of its working tree against HEAD), or None when repo_dir is not in a
    work tree, has no commit yet, git fails, or an untracked file name holds a newline."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    try:
        tree_hash = tree_fingerprint(top, timeout=GIT_TIMEOUT_SECONDS)
    except TreeFingerprintError:
        return None
    return str(top), tree_hash


def reviewed_fingerprint(repo_dir):
    """`fingerprint` with the notes paths the repo's committed list and docs/ name left out: the tree a review
    credits. A bad committed list is named on stderr and leaves only docs/ out. None as `fingerprint` (so
    record_reviewed returns False and is_reviewed is always False there)."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    entries, errors = notes_paths.committed_notes_list(top, timeout=GIT_TIMEOUT_SECONDS)
    for error in errors:
        print("[reviewed-tree] " + error, file=sys.stderr)
    try:
        tree_hash = tree_fingerprint(top, timeout=GIT_TIMEOUT_SECONDS, notes_entries=entries)
    except TreeFingerprintError:
        return None
    return str(top), tree_hash


def read_json_object(file):
    """The JSON object in `file`, or {} when it is missing, unreadable or holds no object."""
    try:
        found = json.loads(file.read_text())
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def read_reviewed(session):
    return read_json_object(reviewed_file(session))


def read_shared_reviewed():
    """Every session's reviewed trees: repo top level -> the latest SHARED_LIMIT fingerprints, oldest first."""
    return read_json_object(shared_reviewed_file())


def record_reviewed(session, repo_dir, tree=None):
    """Store repo_dir's tree as reviewed for the session and in the shared record: `tree`, a stored
    (top, reviewed_fingerprint) pair, when given, else the tree as it stands. Returns False when the tree cannot be
    fingerprinted."""
    found = tree or reviewed_fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    reviewed = read_reviewed(session)
    reviewed[top] = tree_hash
    reviewed_file(session).parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(reviewed_file(session), json.dumps(reviewed) + "\n")

    shared = read_shared_reviewed()
    stored = shared.get(top)
    trees = [value for value in stored if value != tree_hash] if isinstance(stored, list) else []
    shared[top] = [*trees, tree_hash][-SHARED_LIMIT:]
    script_utils.write_text_atomically(shared_reviewed_file(), json.dumps(shared) + "\n")
    return True


def is_reviewed(session, repo_dir):
    """True when repo_dir's working tree, notes paths left out, is exactly a tree that a converged review covered:
    the one recorded for the session, or one in the shared record that any session wrote."""
    found = reviewed_fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    if read_reviewed(session).get(top) == tree_hash:
        return True

    shared_trees = read_shared_reviewed().get(top)
    return isinstance(shared_trees, list) and tree_hash in shared_trees
