#!/usr/bin/env python3
"""SessionStart hook: report an unrestored calibration or mutation seed.

/calibrate and mutation-tester share one lock,
${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json; the old ~/.claude/calibration-lock.json
is read as a fallback (fields file, backup_path, class, ts, kind). The lock is deleted only after the restore is
verified, so a lock
that survives into a new session means the restore never happened, unless the run is still going: the lock also
records worktree (absolute path) and owner_pid. A lock younger than the run timeout whose owner process still
exists (or that names no owner) only gets a note with no restore instruction. Otherwise this hook prints the
absolute paths needed to fix it. A lock with no parseable ts is stale. No lock: no output. Exits 0, except
with `--live`, which prints nothing and exits 0 only when the lock is live (no lock or a stale one: 1).
`--session-pid <pid>`, with or without `--live`, also calls a lock stale when its `writer` is "calibrate" and its
owner_pid is that pid: the caller's session wrote it and, being single-threaded, is no longer inside that /calibrate
step.
"""
import calendar
import os
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
from hook_input import parse_documents_partial, raw_text

# A mutation or calibration run longer than this has been abandoned, whatever its owner process says.
MUTATION_RUN_TIMEOUT_SECONDS = 60 * 60


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
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return None


def pid_is_alive(owner_pid):
    try:
        pid = int(owner_pid)
    except ValueError:
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def session_pid_argument(arguments):
    """The pid after `--session-pid` in the command line, or "" when the caller gave none."""
    if "--session-pid" not in arguments:
        return ""
    position = arguments.index("--session-pid") + 1
    if position >= len(arguments):
        return ""
    return arguments[position]


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


def main():
    live_only = sys.argv[1:2] == ["--live"]
    session_pid = session_pid_argument(sys.argv[1:])
    home = os.environ.get("HOME", "")
    state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(home, ".local", "state")
    lock = os.path.join(state_home, "claude-calibration", "lock.json")
    if not os.path.isfile(lock):
        # A lock left by a run from before the lock moved out of ~/.claude still has to be reported.
        lock = os.path.join(home, ".claude", "calibration-lock.json")
    if not os.path.isfile(lock):
        return 1 if live_only else 0
    try:
        with open(lock, "rb") as handle:
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        text = None

    file = lock_field(text, "file", "?", "?")
    backup = lock_field(text, "backup_path", "?", "?")
    seed_class = lock_field(text, "class", "?", "?")
    stamp = lock_field(text, "ts", "?", "?")
    kind = lock_field(text, "kind", "calibrate", "calibrate")
    worktree = lock_field(text, "worktree", "", "")
    owner_pid = lock_field(text, "owner_pid", "", "")
    writer = lock_field(text, "writer", "", "")

    # The writer records a path relative to its own worktree; name the absolute file so a session in another
    # checkout never restores the wrong one.
    if worktree and file != "?" and not os.path.isabs(file):
        file = os.path.join(worktree, file)

    is_live = lock_is_live(stamp, owner_pid, time.time(), writer, session_pid)
    if live_only:
        return 0 if is_live else 1

    if is_live:
        sys.stdout.buffer.write(live_notice(kind, file, worktree, owner_pid).encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
        return 0

    if kind == "mutation-test":
        what = "MUTATION SEED — a previous mutation-tester run did not finish."
    else:
        what = "CALIBRATION SEED — a previous /calibrate run did not finish."

    message = (
        f"⚠️  UNRESTORED {what}\n"
        "\n"
        f"A deliberate '{seed_class}' mutation was applied at {stamp} and may still be in:\n"
        f"  {file}\n"
        "\n"
        "Restore it from the backup before doing ANY other work in that repo:\n"
        f"  cp \"{backup}\" \"{file}\"\n"
        "\n"
        "Then verify the file is back to what you expect and remove the lock:\n"
        f"  rm \"{lock}\"\n"
        "\n"
        "Do not commit until this is resolved. Do not run /calibrate or dispatch\n"
        "mutation-tester until this lock is gone — both refuse to seed on top of an\n"
        "unrestored seed.\n"
    )
    sys.stdout.buffer.write(message.encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
