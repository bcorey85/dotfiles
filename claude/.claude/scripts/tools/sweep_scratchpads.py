#!/usr/bin/env python3
"""SessionStart hook: delete the temp folders of Claude Code sessions that ended a day ago or more.

Claude Code gives each session a folder at <temp>/claude-<uid>/<project>/<session id>/ (its scratchpad and task
output) and never deletes it, so old ones fill the per-user temp quota. This removes each session folder whose newest
entry is over MAX_AGE_HOURS old, never the folder of the session in the hook input or of any session still running,
and nothing whose name is not a session id. A session is running when a <pid>.json in the sessions folder names it and
that pid is alive; the sessions folder is session_registry.sessions_dir (one file per running session). <temp> is
CLAUDE_CODE_TMPDIR when set, else the system temp folder. Fails open: an error goes to stderr and the hook exits 0.
"""
import json
import os
import re
import shutil
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
import hook_input
import session_registry

MAX_AGE_HOURS = 24
SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def current_session_id():
    """The session id of the hook input, or "" when the input has none."""
    event_text = hook_input.read_stdin_text()
    if not event_text:
        return ""
    event = json.loads(event_text)
    if not isinstance(event, dict):
        return ""
    session_id = event.get("session_id")
    return session_id if isinstance(session_id, str) else ""


def live_session_ids():
    """The ids of the sessions whose <pid>.json in the sessions folder names a live pid. Bad files are skipped."""
    session_ids = (row.get("sessionId") for row in session_registry.live_session_rows())
    return {session_id for session_id in session_ids if isinstance(session_id, str)}


def touched_since(folder, cutoff):
    """Whether the folder or anything under it was modified at or after `cutoff`. Links are not followed."""
    if os.lstat(folder).st_mtime >= cutoff:
        return True
    for parent, names, files in os.walk(folder):
        for name in names + files:
            if os.lstat(os.path.join(parent, name)).st_mtime >= cutoff:
                return True
    return False


def stale_session_folders(root, keep_ids, now):
    """The session folders under `root` untouched for MAX_AGE_HOURS, except those named in `keep_ids`."""
    cutoff = now - MAX_AGE_HOURS * 3600
    stale = []
    for project in os.scandir(root):
        if not project.is_dir(follow_symlinks=False):
            continue
        for session in os.scandir(project.path):
            if not SESSION_ID.fullmatch(session.name) or session.name in keep_ids:
                continue
            if not session.is_dir(follow_symlinks=False):
                continue
            if not touched_since(session.path, cutoff):
                stale.append(session.path)
    return stale


def main():
    # Fail open: a sweep error never blocks the session start.
    try:
        root = hook_input.claude_code_temp_root()
        if not os.path.isdir(root):
            return 0
        keep_ids = live_session_ids()
        keep_ids.add(current_session_id())
        for folder in stale_session_folders(root, keep_ids, time.time()):
            shutil.rmtree(folder, ignore_errors=True)
    except (OSError, ValueError) as error:
        hook_input.emit_stderr(f"{hook_input.hook_name()}: sweep stopped ({error})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
