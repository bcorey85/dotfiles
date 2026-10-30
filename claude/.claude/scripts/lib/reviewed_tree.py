"""The working tree a session's converged review covered, kept per repo so a later commit of that same tree passes.

review_commit_gate.py records the tree when a review-loop ends clean (`review-gate-mark clean`, or /code finishing a
phase) and reads it back at commit time. A tree is its fingerprint, `tree_fingerprint`: "sha256:" and the hash of
`git diff --binary <base> -- .` (git's raw output bytes, never decoded) followed by, for each untracked, non-ignored
file in name order, `\0untracked\0<name>\0<git hash-object>`. Any edit after the review changes the fingerprint.
Verify stores the same value (its context and ledger review rows), with an optional path left out of both parts. The
bytes match what verify stored for any tree whose diff is valid UTF-8; a diff with other bytes in a tracked text edit
hashes differently from before, so verify-prep and the branch review rerun once there.

State: ~/.claude/state/review-gate/<session>.reviewed, one JSON object of repo top level -> fingerprint. A value
written in an older form never equals a current one, so the tree counts as not reviewed until it is recorded again.
"""
import hashlib
import json
import os
import pathlib

import script_utils

GIT_TIMEOUT_SECONDS = 10
REVIEWED_SUFFIX = ".reviewed"


class TreeFingerprintError(Exception):
    """git failed, or the tree holds a file name that cannot be fingerprinted."""


def review_gate_dir():
    return pathlib.Path.home() / ".claude" / "state" / "review-gate"


def reviewed_file(session):
    return review_gate_dir() / (session + REVIEWED_SUFFIX)


def tree_fingerprint(top, base="HEAD", exclude_rel=None, error_type=TreeFingerprintError, timeout=None):
    """Content fingerprint of the working tree at `top` as it stands: `git diff <base>` plus the hash of each
    untracked file, as "sha256:<hex>".

    Equal fingerprints mean equal content, whatever the commits, mtimes or renames in between. `exclude_rel` (a path
    relative to the top level) leaves a file or directory out of both parts. Each git call may run `timeout` seconds
    (None: no limit). Raises error_type when git fails or runs past it, or an untracked file name holds a newline."""
    def git(argv, stdin=None):
        return script_utils.run_or_raise(["git", *argv], error_type, cwd=top, check=True, stdin=stdin,
                                         timeout=timeout, as_bytes=True)

    digest = hashlib.sha256()
    diff_argv = ["diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", base, "--", "."]
    if exclude_rel:
        diff_argv.append(f":(exclude,literal){exclude_rel}")
    digest.update(git(diff_argv).stdout)

    listing = git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout

    def is_excluded(name):
        return bool(exclude_rel) and script_utils.path_is_under(os.fsdecode(name), exclude_rel)

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
    """(repo top level, fingerprint of its working tree against HEAD), or None when repo_dir is not in a work tree,
    has no commit yet, git fails, or an untracked file name holds a newline (so record_reviewed returns False and
    is_reviewed is always False there)."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    try:
        tree_hash = tree_fingerprint(top, timeout=GIT_TIMEOUT_SECONDS)
    except TreeFingerprintError:
        return None
    return str(top), tree_hash


def read_reviewed(session):
    try:
        reviewed = json.loads(reviewed_file(session).read_text())
    except (OSError, ValueError):
        return {}
    return reviewed if isinstance(reviewed, dict) else {}


def record_reviewed(session, repo_dir):
    """Store repo_dir's tree as reviewed for the session. Returns False when the tree cannot be fingerprinted."""
    found = fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    reviewed = read_reviewed(session)
    reviewed[top] = tree_hash
    reviewed_file(session).parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(reviewed_file(session), json.dumps(reviewed) + "\n")
    return True


def is_reviewed(session, repo_dir):
    """True when repo_dir's working tree is exactly the tree recorded as reviewed for the session."""
    found = fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    return read_reviewed(session).get(top) == tree_hash
