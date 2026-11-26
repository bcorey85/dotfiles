"""session_registry.py: the live Claude Code session registry and the config folders it sits in.

A live session has one `<pid>.json` row in the sessions folder (fields `name`, `sessionId`, `pid`);
`row_for_name` and `row_for_session_id` find one live row. The sessions and projects folders
are under `$CLAUDE_CONFIG_DIR` when it is set, else under the home config folder. Standard library and
`process_group` and `script_utils` only (neither imports any other toolkit module at load time)."""
import json
import os
import pathlib

import script_utils
from process_group import pid_is_alive


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


def session_subagents_dir(session_id):
    """The `subagents` folder of a session's transcripts (first match under any project), None when it has none."""
    for folder in projects_dir().glob(f"*/{session_id}/subagents"):
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


def other_live_sessions_in(folder, own_session_id):
    """Every live registry row of a session other than `own_session_id` whose `cwd` is `folder` or inside it, in
    registry order. A row with no string `cwd` is no match."""
    folder_path = pathlib.Path(folder).resolve()
    found = []
    for row in live_session_rows():
        if row.get("sessionId") == own_session_id:
            continue
        cwd = row.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            continue
        if pathlib.Path(cwd).resolve().is_relative_to(folder_path):
            found.append(row)
    return found


def other_live_session_in(folder, own_session_id):
    """The first row of `other_live_sessions_in` (registry file order); None when there is none. It is matched by
    working folder alone, so it says nothing about who wrote a file."""
    found = other_live_sessions_in(folder, own_session_id)
    if not found:
        return None
    return found[0]


def session_transcript(session_id):
    """The transcript file of a session (first match in sorted order under any project), None when it has none or
    `session_id` is not a non-empty string."""
    if not isinstance(session_id, str) or not session_id:
        return None
    found = sorted(projects_dir().glob(f"*/{session_id}.jsonl"))
    if not found:
        return None
    return found[0]


def session_transcripts(session_id):
    """The transcript of a session and the transcripts of its subagents (coder dispatches edit through them); empty
    when the session has no main transcript."""
    transcript = session_transcript(session_id)
    if transcript is None:
        return []
    subagent_pattern = pathlib.Path(script_utils.subagent_transcript_path(str(transcript), "*"))
    subagent_matches = subagent_pattern.parent.glob(subagent_pattern.name)
    subagent_transcripts = sorted(subagent_matches)
    return [transcript, *subagent_transcripts]


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
