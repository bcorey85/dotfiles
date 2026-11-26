"""session_registry.py: the live Claude Code session registry and the config folders it sits in.

A live session has one `<pid>.json` row in the sessions folder (fields `name`, `sessionId`, `pid`);
`row_for_name` and `row_for_session_id` find one live row. The sessions and projects folders
are under `$CLAUDE_CONFIG_DIR` when it is set, else under the home config folder. Standard library and
`process_group` only."""
import json
import os
import pathlib

from process_group import pid_is_alive

SUBAGENTS_DIR_NAME = "subagents"


def config_dir_override():
    """`$CLAUDE_CONFIG_DIR` as a path, or None when it is unset or empty."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config_dir:
        return None
    return pathlib.Path(config_dir)


def sessions_dir():
    """The live-session registry folder: `$CLAUDE_CONFIG_DIR/sessions`, else the home config's sessions folder."""
    override = config_dir_override()
    if override is not None:
        return override / "sessions"
    return pathlib.Path.home() / ".claude" / "sessions"


def projects_dir():
    """The transcript folder: `$CLAUDE_CONFIG_DIR/projects`, else the home config's projects folder."""
    override = config_dir_override()
    if override is not None:
        return override / "projects"
    return pathlib.Path.home() / ".claude" / "projects"


def session_transcripts(session_id):
    """Every `<projects folder>/*/<session_id>.jsonl`, sorted."""
    return sorted(projects_dir().glob(f"*/{session_id}.jsonl"))


def session_subagents_dir(session_id):
    """The `subagents` folder of a session's transcripts (first match under any project), None when it has none."""
    for folder in projects_dir().glob(f"*/{session_id}/{SUBAGENTS_DIR_NAME}"):
        return folder
    return None


def live_session_rows():
    """The readable `<pid>.json` rows of the registry folder whose pid is alive. A row that is not a JSON object with
    an integer `pid` (not a bool) is not a registry row (the folder also holds `.key` files) and is left out."""
    rows = []
    for row_file in sorted(sessions_dir().glob("*.json")):
        try:
            row = json.loads(row_file.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        pid = row.get("pid")
        if isinstance(pid, int) and not isinstance(pid, bool) and pid_is_alive(pid):
            rows.append(row)
    return rows


def row_for_name(name):
    """The first live row (file order, as `live_session_rows`) named `name`; None when none is."""
    for row in live_session_rows():
        if row.get("name") == name:
            return row
    return None


def row_for_session_id(session_id):
    """The one live row whose `sessionId` equals `session_id`; None when no live row holds it."""
    for row in live_session_rows():
        if row.get("sessionId") == session_id:
            return row
    return None


def other_live_session_in(folder, own_session_id):
    """The first live registry row of a session other than `own_session_id` whose `cwd` is `folder` or inside it;
    None when there is none. A row with no string `cwd` is no match."""
    folder_path = pathlib.Path(folder).resolve()
    for row in live_session_rows():
        if row.get("sessionId") == own_session_id:
            continue
        cwd = row.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            continue
        if pathlib.Path(cwd).resolve().is_relative_to(folder_path):
            return row
    return None


def holder_label(row):
    """What names the live session of a registry row: its name, else its session id, else its pid, else
    `unknown session`."""
    pid = row.get("pid")
    return row.get("name") or row.get("sessionId") or (f"pid {pid}" if pid is not None else "unknown session")


def session_display_name(session_id):
    """The name ListAgents shows for a live Claude Code session, read from the live registry rows. None when no
    live row holds that session id with a non-empty name."""
    for row in live_session_rows():
        if row.get("sessionId") == session_id and row.get("name"):
            return row["name"]
    return None
