#!/usr/bin/env python3
"""SessionStart hook: report an unrestored calibration or mutation seed.

/calibrate and mutation-tester share one lock, owned by lib/calibration_lock.py (path, fallback, fields). The
lock is deleted only after the restore is verified, so a lock that survives into a new session means the restore
never happened, unless the run is still going: the lock also records worktree (absolute path) and owner_pid. A
lock younger than the run timeout whose owner process still exists (or that names no owner) only gets a note
with no restore instruction. Otherwise this hook prints the absolute paths needed to fix it. A lock with no
parseable ts is stale. No lock: no output. Exits 0, except with `--live`, which prints nothing and exits 0 only
when the lock is live (no lock or a stale one: 1).
`--session-pid <pid>`, with or without `--live`, also calls a lock stale when its `writer` is "calibrate" and its
owner_pid is that pid: the caller's session wrote it and, being single-threaded, is no longer inside that /calibrate
step.
"""
import os
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import calibration_lock


def session_pid_argument(arguments):
    """The pid after `--session-pid` in the command line, or "" when the caller gave none."""
    if "--session-pid" not in arguments:
        return ""
    position = arguments.index("--session-pid") + 1
    if position >= len(arguments):
        return ""
    return arguments[position]


def main():
    live_only = sys.argv[1:2] == ["--live"]
    session_pid = session_pid_argument(sys.argv[1:])
    lock = calibration_lock.find_lock()
    if lock is None:
        return 1 if live_only else 0
    text = calibration_lock.read_lock_text(lock)
    view = calibration_lock.read_lock_view(text)

    is_live = calibration_lock.lock_is_live(view.stamp, view.owner_pid, time.time(), view.writer, session_pid)
    if live_only:
        return 0 if is_live else 1

    if is_live:
        notice = calibration_lock.live_notice(view.kind, view.file, view.worktree, view.owner_pid)
        sys.stdout.buffer.write(notice.encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
        return 0

    message = calibration_lock.unrestored_message(view, lock)
    sys.stdout.buffer.write(message.encode("utf-8", "replace"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
