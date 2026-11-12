"""The working tree a session's converged review covered, kept per repo so a later commit of that same tree passes.

A review-loop records its tree when it ends clean: the scripted loop at its hand-back
(review_loop_packet.write_handback_rows). Then
review_commit_gate.py reads it back at commit time. A tree is its fingerprint, `tree_fingerprint`: "sha256:" and the
hash of `git diff --binary --no-renames --diff-filter=a <base> -- .` (git's raw output bytes, never decoded)
followed by, for each file the tree adds against base (committed since base, staged as new, or untracked and
non-ignored) in name order, `\0untracked\0<name>\0<git hash-object>`. An added submodule stays in the diff part; an
added symlink, staged, committed or untracked, is hashed as `\0symlink\0<name>\0<link text>`. An untracked
nested repository raises.
A `git add` of a new file, a new symlink or a staged move leaves the value as it was; `git rm --cached` changes it.
The reviewed tree leaves the repo's notes paths (notes_paths.py) out of both parts, so an edit of a plan or note
after the review keeps the credit and any other edit voids it.
Verify stores the `tree_fingerprint` whole-tree value (its context and ledger review rows), not the reviewed value,
with an optional path left out of both parts. A
tree whose added paths are all untracked regular files keeps its old value; a tree that adds a file through the
index or a commit since base hashes differently, so verify-prep and the branch review rerun once there.

State: ~/.claude/state/review-gate/<session>.reviewed, one JSON object of repo top level -> fingerprint, and
~/.claude/state/review-gate/reviewed-trees.json, repo top level -> the latest fingerprints any session recorded. A value
written in the older form for a tree that adds a file through the index or a commit since base never equals a current
one, so that tree counts as not reviewed until it is recorded again; a tree whose added paths are all untracked
regular files keeps its old value.
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
# Added submodules (160000) are not hashed as files; they stay in the patch. Symlinks (120000) are hashed by link text.
PATCH_MODES = {b"160000"}
SYMLINK_MODE = b"120000"
# The fingerprint of a work tree with no change against its base: nothing was hashed.
NO_CHANGE_FINGERPRINT = "sha256:" + hashlib.sha256().hexdigest()


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
    """Content fingerprint of the working tree at `top` as it stands: `git diff <base>` without added files, plus the
    hash of each file the tree adds against `base` (committed since `base`, staged as new, or untracked), as
    "sha256:<hex>"; an added submodule stays in the diff, an added symlink is hashed by its link text whether staged,
    committed or untracked, and an untracked nested repository raises.

    Equal fingerprints mean equal content, whatever the mtimes or renames in between, and a `git add` of a new file,
    a new symlink or a staged move leaves the value as it was. `git rm --cached` of a tracked file changes it.
    `exclude_rel` (a path relative to the top level) leaves a file or directory out of both parts. `notes_entries`,
    a list of `.claude/notes-paths` entries, leaves every notes path they and docs/ name out of both parts; None
    leaves them in. Each git call may run `timeout` seconds (None: no limit). Raises error_type when git fails or
    runs past it, or an added file name holds a newline."""
    def git(argv, stdin=None):
        return script_utils.run_or_raise(["git", *argv], error_type, cwd=top, check=True, stdin=stdin,
                                         timeout=timeout, as_bytes=True)

    digest = hashlib.sha256()
    pathspecs = ["--", "."]
    if exclude_rel:
        pathspecs.append(f":(exclude,literal){exclude_rel}")
    if notes_entries is not None:
        pathspecs += notes_paths.exclude_pathspecs(notes_entries)
    # Lowercase `a` leaves added files out of the diff: they are hashed below as whole files, so a staged new file
    # and an untracked one give the same value. --no-renames makes a staged move read as a delete plus an add.
    diff_flags = ["--binary", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames"]
    digest.update(git(["diff", *diff_flags, "--diff-filter=a", base, *pathspecs]).stdout)

    raw = git(["diff", "--raw", "-z", "--no-renames", "--diff-filter=A", base, *pathspecs]).stdout
    added, added_links, in_patch = added_paths(raw)
    added = [*added, *added_links]
    listing = git(["ls-files", "--others", "--exclude-standard", "-z"]).stdout

    def is_excluded(name):
        path = os.fsdecode(name)
        if exclude_rel and script_utils.path_is_under(path, exclude_rel):
            return True
        return notes_entries is not None and notes_paths.is_notes_path(path, notes_entries)

    # An added submodule is a directory, so it stays in the patch instead of being hashed as a whole file.
    kept_in_patch = sorted(name for name in in_patch if not is_excluded(name))
    if kept_in_patch:
        patch_specs = ["--", *[":(literal)" + os.fsdecode(name) for name in kept_in_patch]]
        digest.update(git(["diff", *diff_flags, "--diff-filter=A", base, *patch_specs]).stdout)

    untracked = [name for name in listing.split(b"\0") if name]
    nested = [name for name in untracked if name.endswith(b"/") and not is_excluded(name)]
    if nested:
        raise error_type("an untracked nested repository cannot be fingerprinted: " + os.fsdecode(nested[0]))

    def work_path(name):
        rel = os.fsdecode(name)
        return os.path.join(top, rel)

    # Every symlink, staged, committed or untracked, is hashed by its link text: hash-object would follow it.
    link_names = set(added_links)
    for name in untracked:
        if os.path.islink(work_path(name)):
            link_names.add(name)
    names = sorted(name for name in {*added, *untracked} if not is_excluded(name))
    if any(b"\n" in name for name in names):
        raise error_type("an added file name holds a newline; rename it so the tree can be fingerprinted")

    file_names = [name for name in names if name not in link_names]
    file_entries = {}
    if file_names:
        paths_input = b"\n".join(file_names) + b"\n"
        hashed = git(["hash-object", "--stdin-paths"], stdin=paths_input)
        file_hashes = hashed.stdout.split()
        if len(file_hashes) != len(file_names):
            raise error_type(f"git hash-object returned {len(file_hashes)} hashes for {len(file_names)} added files")
        # The label stays "untracked" for staged and committed files too: stored values hold these bytes.
        file_entries = dict(zip(file_names, file_hashes, strict=True))
    for name in names:
        if name in link_names:
            target = os.readlink(work_path(name))
            digest.update(b"\0symlink\0" + name + b"\0" + os.fsencode(target))
        else:
            digest.update(b"\0untracked\0" + name + b"\0" + file_entries[name])
    return "sha256:" + digest.hexdigest()


def added_paths(raw):
    """(files, links, in_patch) from `git diff --raw -z --diff-filter=A` output: the added paths to hash as whole
    files, the added symlinks, which are hashed by their link text, and the added submodules, which stay in the
    patch."""
    raw_fields = [field for field in raw.split(b"\0") if field]
    files = []
    links = []
    in_patch = []
    # With -z and no renames, each entry is a ":<old mode> <new mode> ..." field and then one path field.
    for meta, name in zip(raw_fields[0::2], raw_fields[1::2], strict=True):
        new_mode = meta.split()[1]
        if new_mode in PATCH_MODES:
            in_patch.append(name)
        elif new_mode == SYMLINK_MODE:
            links.append(name)
        else:
            files.append(name)
    return files, links, in_patch


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
    work tree, has no commit yet, git fails, an added file name holds a newline, or the tree holds an untracked
    nested repository."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    try:
        tree_hash = tree_fingerprint(top, timeout=GIT_TIMEOUT_SECONDS)
    except TreeFingerprintError:
        return None
    return str(top), tree_hash


def reviewed_fingerprint(repo_dir, base="HEAD"):
    """`fingerprint` with the notes paths the repo's committed list and docs/ name left out: the tree a review
    credits, as a change against `base`. A bad committed list is named on stderr and leaves only docs/ out. None as
    `fingerprint` (so record_reviewed returns False and is_reviewed is always False there)."""
    top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS)
    if top is None:
        return None

    entries, errors = notes_paths.committed_notes_list(top, timeout=GIT_TIMEOUT_SECONDS)
    for error in errors:
        print("[reviewed-tree] " + error, file=sys.stderr)
    try:
        tree_hash = tree_fingerprint(top, base=base, timeout=GIT_TIMEOUT_SECONDS, notes_entries=entries)
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


def is_reviewed(session, repo_dir, tree=None):
    """True when repo_dir's working tree, notes paths left out, is exactly a tree that a converged review covered:
    the one recorded for the session, or one in the shared record that any session wrote. `tree` is a
    (top, hash) pair that `reviewed_fingerprint` already returned, used in place of fingerprinting again."""
    found = tree or reviewed_fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    if read_reviewed(session).get(top) == tree_hash:
        return True

    return shared_record_holds(top, tree_hash)


def shared_record_holds(top, tree_hash):
    """True when the shared record, which any session wrote, lists `tree_hash` for the repo top level `top`."""
    shared_trees = read_shared_reviewed().get(top)
    return isinstance(shared_trees, list) and tree_hash in shared_trees


def shared_record_covers(repo_dir):
    """True when repo_dir's uncommitted change against HEAD, notes paths left out, is in the shared reviewed record:
    the read `is_reviewed` does with no session. When the tree has no change against HEAD, the change the last commit
    made (the tree against HEAD~1) is read instead, so a credit survives committing the reviewed change (never when
    HEAD is a merge commit). False when the tree cannot be fingerprinted, and False for the empty-change value: it
    sits in the record of many repos, and covering it would credit every commit made since a review."""
    found = reviewed_fingerprint(repo_dir)
    if found is None:
        return False
    top, tree_hash = found
    if tree_hash != NO_CHANGE_FINGERPRINT:
        return shared_record_holds(top, tree_hash)

    committed_hash = last_commit_fingerprint(top)
    if committed_hash is None or committed_hash == NO_CHANGE_FINGERPRINT:
        return False
    return shared_record_holds(top, committed_hash)


def last_commit_fingerprint(top):
    """The fingerprint of the work tree at `top` against HEAD~1, notes paths left out as `reviewed_fingerprint` does;
    None when HEAD has no parent, is a merge (its change would be a whole merged-in branch), or the tree cannot be
    fingerprinted."""
    # Fails closed: a git failure or timeout, a root commit and a merge all give None, so none of them earns credit.
    parents_line = script_utils.git_output(top, "rev-list", "--parents", "-n", "1", "HEAD",
                                           timeout=GIT_TIMEOUT_SECONDS)
    if parents_line is None:
        return None
    tokens = parents_line.split()
    if len(tokens) != 2:
        return None
    parent = tokens[1]

    found = reviewed_fingerprint(top, base=parent)
    if found is None:
        return None
    return found[1]
