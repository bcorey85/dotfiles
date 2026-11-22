#!/usr/bin/env python3
"""session_pane.py: name the Claude Code session that runs a command, as JSON on stdout.

Usage: session_pane.py sender

Prints {"name": "<ListAgents name>"} and exits 0 when the name is found. The name comes from
$CLAUDE_CODE_SESSION_ID, else from the session id of the herdr pane the command runs in (`herdr-api pane current`),
each looked up through session_registry.session_display_name.
Otherwise it prints {"name": null, "reason": "<why>"}: exit 1 when neither source gives a name, exit 2 when the
herdr-api call fails (the reason names the call). Callers read `.name` and `.reason`, never stderr."""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import session_registry

EXIT_NO_NAME = 1
EXIT_TOOL_FAILED = 2
PANE_CURRENT_CALL = "herdr-api pane current"


class PaneCallError(Exception):
    """The herdr-api call failed; the message names the call."""


def pane_session_id():
    """The session id of the current herdr pane's agent, or "" when the pane has none. Raises PaneCallError when
    herdr-api is missing, exits non-zero or prints no JSON object."""
    try:
        finished = subprocess.run(["herdr-api", "pane", "current"], capture_output=True, text=True)
    except OSError as error:
        raise PaneCallError(f"{PANE_CURRENT_CALL} failed: {error}") from error
    if finished.returncode != 0:
        raise PaneCallError(f"{PANE_CURRENT_CALL} failed with exit {finished.returncode}")

    try:
        reply = json.loads(finished.stdout)
    except ValueError as error:
        raise PaneCallError(f"{PANE_CURRENT_CALL} printed no JSON: {error}") from error
    if not isinstance(reply, dict):
        raise PaneCallError(f"{PANE_CURRENT_CALL} printed no JSON object")

    result = reply.get("result")
    pane = result.get("pane") if isinstance(result, dict) else None
    agent_session = pane.get("agent_session") if isinstance(pane, dict) else None
    session_id = agent_session.get("value") if isinstance(agent_session, dict) else None
    return session_id if isinstance(session_id, str) else ""


def found(name):
    print(json.dumps({"name": name}))
    return 0


def not_found(reason, status):
    print(json.dumps({"name": None, "reason": reason}))
    return status


def sender():
    env_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if env_session_id:
        env_name = session_registry.session_display_name(env_session_id)
        if env_name:
            return found(env_name)

    try:
        session_id = pane_session_id()
    except PaneCallError as error:
        return not_found(str(error), EXIT_TOOL_FAILED)
    if not session_id:
        return not_found("no CLAUDE_CODE_SESSION_ID name and the current pane has no agent session",
                         EXIT_NO_NAME)

    pane_name = session_registry.session_display_name(session_id)
    if not pane_name:
        return not_found(f"no live named session holds session id {session_id}", EXIT_NO_NAME)
    return found(pane_name)


def main(argv):
    if argv[1:] != ["sender"]:
        print(__doc__, file=sys.stderr)
        return 2
    return sender()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
