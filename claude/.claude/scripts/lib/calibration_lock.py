"""calibration_lock.py: owner of the calibration and mutation lock format. Import it; never read or write the lock
another way.

/calibrate and mutation-tester share one lock file,
${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json. The old ~/.claude/calibration-lock.json is
read as a fallback only, never written. Backups live in <state folder>/backups/<file>.

Fields of the lock (a JSON object):
  ts           string  UTC time of the write, STAMP_FORMAT
  kind         string  "mutation-test" (mutation-tester); a missing kind reads as "calibrate"
  writer       string  "mutation-tester"; "calibrate" for a /calibrate lock
  file         string  target path relative to worktree, POSIX form
  backup_path  string  absolute <state folder>/backups/<file>
  pre_hash     string  first 16 hex characters of the sha256 of the target's bytes
  class        string  "mutant: " + the mutation class
  line         string  the line the mutation touches, as given
  worktree     string  absolute path of the git work tree that holds the target
  owner_pid    int     process that owns the run
The agent's jq writer still writes the old backups/<basename>.bak layout and may write `file` as an absolute
path; read_lock_view accepts both. Drop this note when the writer moves to mutation_lock.py.
A lock with no parseable ts is stale. A lock younger than MUTATION_RUN_TIMEOUT_SECONDS whose owner process still
exists (or that names no owner) is live.
"""
import calendar
import hashlib
import os
import pathlib
import time
from typing import NamedTuple

from hook_input import parse_documents_partial, raw_text
from process_group import pid_is_alive

STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# A mutation or calibration run longer than this has been abandoned, whatever its owner process says.
MUTATION_RUN_TIMEOUT_SECONDS = 60 * 60
LOCK_WAIT_SECONDS = 5
MUTATION_KIND = "mutation-test"
MUTATION_WRITER = "mutation-tester"
PRE_HASH_LENGTH = 16


def pre_hash(file):
    """The lock's pre_hash for a file: the first PRE_HASH_LENGTH hex characters of the sha256 of its bytes."""
    return hashlib.sha256(pathlib.Path(file).read_bytes()).hexdigest()[:PRE_HASH_LENGTH]


def _home(environ):
    return environ.get("HOME", "")


def state_folder(environ=None):
    """The folder that holds the lock and its backups.
    Paths are strings joined from the raw environment text, so the guard prints them untidied."""
    environ = os.environ if environ is None else environ
    state_home = environ.get("XDG_STATE_HOME") or os.path.join(_home(environ), ".local", "state")
    return os.path.join(state_home, "claude-calibration")


def lock_path(environ=None):
    return os.path.join(state_folder(environ), "lock.json")


def legacy_lock_path(environ=None):
    environ = os.environ if environ is None else environ
    return os.path.join(_home(environ), ".claude", "calibration-lock.json")


def backups_folder(environ=None):
    return os.path.join(state_folder(environ), "backups")


def backup_path(file, environ=None):
    """The backup of a work-tree-relative file. Joined as a string: a Path would tidy "//" and "/./" out of the
    state root, and a lock records the untidied text."""
    return os.path.join(backups_folder(environ), file)


def find_lock(environ=None):
    """The lock file to read: the state path first, then the legacy path; None when neither is a file."""
    current = lock_path(environ)
    if os.path.isfile(current):
        return current
    # A lock left by a run from before the lock moved out of ~/.claude still has to be reported.
    legacy = legacy_lock_path(environ)
    if os.path.isfile(legacy):
        return legacy
    return None


def read_lock_text(path):
    """The lock's text (utf-8, undecodable bytes replaced), or None when it cannot be read."""
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return None


def lock_field(text, key, default, fallback):
    """`jq -r '.key // default' lock 2>/dev/null || echo fallback`, as a shell variable holds it.
    text is None when the lock could not be read: jq fails and the fallback is all there is."""
    if text is None:
        return fallback
    documents, broken = parse_documents_partial(text)
    pieces = []
    failed = broken
    for document in documents:
        if document is None:
            value = None
        elif isinstance(document, dict):
            value = document.get(key)
        else:
            failed = True
            break
        if value is None or value is False:
            value = default
        pieces.append(raw_text(value))
    if failed:
        pieces.append(fallback)
    return "\n".join(pieces).rstrip("\n")


def parse_stamp(stamp):
    """Epoch seconds of the lock's UTC `ts` (jq `todate` form), or None when it does not parse."""
    try:
        return calendar.timegm(time.strptime(stamp, STAMP_FORMAT))
    except ValueError:
        return None


def format_stamp(epoch):
    """The lock's `ts` text for an epoch in seconds."""
    return time.strftime(STAMP_FORMAT, time.gmtime(epoch))


def lock_is_live(stamp, owner_pid, now, writer="", session_pid=""):
    """A lock is live while its run can still be going: younger than the run timeout, and, when the lock names
    an owner process, that process still exists. A lock with no owner, or with a `ts` that does not parse, is
    live only when its age proves it. A lock written by /calibrate in the caller's own session is stale: the
    session is single-threaded, so the caller running now means that step is over. A lock written by
    mutation-tester stays live in the same session, since it can run in the background."""
    written = parse_stamp(stamp)
    if written is None or now - written > MUTATION_RUN_TIMEOUT_SECONDS:
        return False
    if writer == "calibrate" and session_pid != "" and owner_pid == session_pid:
        return False
    if owner_pid == "":
        return True
    return pid_is_alive(owner_pid)


class LockView(NamedTuple):
    file: str
    backup: str
    seed_class: str
    stamp: str
    kind: str
    worktree: str
    owner_pid: str
    writer: str


def read_lock_view(text):
    """The lock's fields with the guard's defaults. The writer records a path relative to its own worktree;
    the view names the absolute file so a session in another checkout never restores the wrong one."""
    file = lock_field(text, "file", "?", "?")
    worktree = lock_field(text, "worktree", "", "")
    if worktree and file != "?" and not os.path.isabs(file):
        file = os.path.join(worktree, file)
    return LockView(
        file=file,
        backup=lock_field(text, "backup_path", "?", "?"),
        seed_class=lock_field(text, "class", "?", "?"),
        stamp=lock_field(text, "ts", "?", "?"),
        kind=lock_field(text, "kind", "calibrate", "calibrate"),
        worktree=worktree,
        owner_pid=lock_field(text, "owner_pid", "", ""),
        writer=lock_field(text, "writer", "", ""),
    )


def live_notice(kind, file, worktree, owner_pid):
    owner = f"process {owner_pid}" if owner_pid else "another session"
    place = f" in {worktree}" if worktree else ""
    return (
        f"Note: a {kind} seed is in progress{place} (owner: {owner}); it touches\n"
        f"  {file}\n"
        "Do not restore it or remove the lock — the run is still live. If it is not, the lock is\n"
        f"reported as unrestored once it is older than {MUTATION_RUN_TIMEOUT_SECONDS // 60} minutes\n"
        "or its owner process is gone.\n"
    )


def recovery_commands(view, lock):
    """The two shell commands that undo a seed by hand: (copy the backup over the file, remove the lock)."""
    return f"cp \"{view.backup}\" \"{view.file}\"", f"rm \"{lock}\""


def unrestored_message(view, lock):
    """The text for a lock whose run is over: where the seed may still be, and the commands that undo it."""
    copy_command, remove_command = recovery_commands(view, lock)
    if view.kind == MUTATION_KIND:
        what = "MUTATION SEED — a previous mutation-tester run did not finish."
    else:
        what = "CALIBRATION SEED — a previous /calibrate run did not finish."
    return (
        f"⚠️  UNRESTORED {what}\n"
        "\n"
        f"A deliberate '{view.seed_class}' mutation was applied at {view.stamp} and may still be in:\n"
        f"  {view.file}\n"
        "\n"
        "Restore it from the backup before doing ANY other work in that repo:\n"
        f"  {copy_command}\n"
        "\n"
        "Then verify the file is back to what you expect and remove the lock:\n"
        f"  {remove_command}\n"
        "\n"
        "Do not commit until this is resolved. Do not run /calibrate or dispatch\n"
        "mutation-tester until this lock is gone — both refuse to seed on top of an\n"
        "unrestored seed.\n"
    )
