#!/usr/bin/env python3
"""SessionStart hook: delete the temp folders of Claude Code sessions that ended a day ago or more.

Claude Code gives each session a folder at <temp>/claude-<uid>/<project>/<session id>/ (its scratchpad and task
output) and never deletes it, so old ones fill the per-user temp quota. This removes each session folder whose newest
entry is over MAX_AGE_HOURS old, never the folder of the session in the hook input, and nothing whose name is not a
session id. <temp> is CLAUDE_CODE_TMPDIR when set, else the system temp folder. Fails open: an error goes to stderr
and the hook exits 0.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
import hook_input

MAX_AGE_HOURS = 24
SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def temp_root():
    """The folder that holds the per-project session folders."""
    base = os.environ.get("CLAUDE_CODE_TMPDIR") or tempfile.gettempdir()
    return os.path.join(base, f"claude-{os.getuid()}")


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


def touched_since(folder, cutoff):
    """Whether the folder or anything under it was modified at or after `cutoff`. Links are not followed."""
    if os.lstat(folder).st_mtime >= cutoff:
        return True
    for parent, names, files in os.walk(folder):
        for name in names + files:
            if os.lstat(os.path.join(parent, name)).st_mtime >= cutoff:
                return True
    return False


def stale_session_folders(root, keep_id, now):
    """The session folders under `root` untouched for MAX_AGE_HOURS, except `keep_id`'s."""
    cutoff = now - MAX_AGE_HOURS * 3600
    stale = []
    for project in os.scandir(root):
        if not project.is_dir(follow_symlinks=False):
            continue
        for session in os.scandir(project.path):
            if not SESSION_ID.fullmatch(session.name) or session.name == keep_id:
                continue
            if not session.is_dir(follow_symlinks=False):
                continue
            if not touched_since(session.path, cutoff):
                stale.append(session.path)
    return stale


def main():
    # Fail open: a sweep error never blocks the session start.
    try:
        root = temp_root()
        if not os.path.isdir(root):
            return 0
        keep_id = current_session_id()
        for folder in stale_session_folders(root, keep_id, time.time()):
            shutil.rmtree(folder, ignore_errors=True)
    except (OSError, ValueError) as error:
        hook_input.emit_stderr(f"{hook_input.hook_name()}: sweep stopped ({error})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
