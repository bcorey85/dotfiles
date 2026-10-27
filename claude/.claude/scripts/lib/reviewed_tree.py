"""The working tree a session's converged review covered, kept per repo so a later commit of that same tree passes.

review_commit_gate.py records the tree when a review-loop ends clean (`review-gate-mark clean`, or /code finishing a
phase) and reads it back at commit time. A tree is its fingerprint: a hash of `git diff HEAD --binary` plus the name
and content hash of every untracked, non-ignored file. Any edit after the review changes the fingerprint.

State: ~/.claude/state/review-gate/<session>.reviewed, one JSON object of repo top level -> fingerprint.
"""
import hashlib
import json
import os
import pathlib

import script_utils

GIT_TIMEOUT_SECONDS = 10
REVIEWED_SUFFIX = ".reviewed"


def review_gate_dir():
    return pathlib.Path(os.environ["HOME"]) / ".claude" / "state" / "review-gate"


def reviewed_file(session):
    return review_gate_dir() / (session + REVIEWED_SUFFIX)


def fingerprint(repo_dir):
    """(repo top level, fingerprint of its working tree against HEAD), or None when repo_dir is not in a work tree,
    has no commit yet, or git fails."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    tracked_diff = script_utils.git_output(repo_dir, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-renames",
                                           timeout=GIT_TIMEOUT_SECONDS)
    untracked = script_utils.git_output(repo_dir, "ls-files", "--others", "--exclude-standard", "--full-name", "-z",
                                        timeout=GIT_TIMEOUT_SECONDS)
    if top is None or tracked_diff is None or untracked is None:
        return None

    digest = hashlib.sha256(tracked_diff.encode("utf-8", "surrogateescape"))
    for name in sorted(path for path in untracked.split("\0") if path):
        content_hash = script_utils.git_output(top, "hash-object", "--", name, timeout=GIT_TIMEOUT_SECONDS)
        if content_hash is None:
            return None
        digest.update(f"\0{name}\0{content_hash}".encode("utf-8", "surrogateescape"))
    return str(top), digest.hexdigest()


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
