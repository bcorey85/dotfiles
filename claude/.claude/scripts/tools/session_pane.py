#!/usr/bin/env python3
"""session_pane.py: name the Claude Code session that runs a command, or resolve a target to its pane.

Both answers are JSON on stdout.

Usage: session_pane.py sender
       session_pane.py resolve ARG

resolve prints {"pane_id": "...", "via": "path"|"session"|"as-given"}. An ARG that contains "/" and is an existing
directory gives the one claude agent running inside it; else a live session name gives the agent that holds its
session id (a bare name is always a session name, even when a folder of that name exists); else ARG is returned as
given. Exit 1 with a message on stderr when a directory holds no claude agent or several (each listed as
`pane_id cwd`), or when the session has no pane; exit 2 when `herdr-api agent list` fails.

sender prints {"name": "<ListAgents name>"} and exits 0 when the name is found. The name comes from
$CLAUDE_CODE_SESSION_ID, else from the session id of the herdr pane the command runs in (`herdr-api pane current`),
each looked up through session_registry.session_display_name.
Otherwise it prints {"name": null, "reason": "<why>"}: exit 1 when neither source gives a name, exit 2 when the
herdr-api call fails (the reason names the call). Callers read `.name` and `.reason`, never stderr."""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import session_registry
from herdr_agents import PaneCallError, agents_in, claude_agents, herdr_reply

EXIT_NO_NAME = 1
EXIT_TOOL_FAILED = 2
VIA_PATH = "path"
VIA_SESSION = "session"
VIA_AS_GIVEN = "as-given"


def pane_session_id():
    """The session id of the current herdr pane's agent, or "" when the pane has none. Raises PaneCallError when
    herdr-api is missing, exits non-zero or prints no JSON object."""
    reply = herdr_reply(["pane", "current"])
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


def resolved(pane_id, via):
    print(json.dumps({"pane_id": pane_id, "via": via}))
    return 0


def resolve_path(directory, agents):
    """The pane of the one claude agent whose cwd is inside `directory`. Prints why and returns an exit code when
    there is none or several."""
    inside = agents_in(directory, agents)
    if not inside:
        print(f"no claude agent runs in {directory}", file=sys.stderr)
        return EXIT_NO_NAME
    if len(inside) > 1:
        print(f"{len(inside)} claude agents run in {directory}; name one by pane id:", file=sys.stderr)
        for agent in inside:
            print(f"{agent.get('pane_id')} {agent.get('cwd')}", file=sys.stderr)
        return EXIT_NO_NAME
    return resolved(inside[0].get("pane_id"), VIA_PATH)


def resolve_session(row, name, agents):
    """The pane of the claude agent that holds the session id of registry row `row`."""
    session_id = row.get("sessionId")
    for agent in agents:
        agent_session = agent.get("agent_session")
        if isinstance(agent_session, dict) and agent_session.get("value") == session_id:
            return resolved(agent.get("pane_id"), VIA_SESSION)
    print(f"session {name} has no herdr pane", file=sys.stderr)
    return EXIT_NO_NAME


def names_a_directory(arg):
    """True for an argument with a "/" that is an existing directory; a bare name is never a path."""
    return "/" in arg and os.path.isdir(arg)


def resolve(arg):
    """A path (an argument with a "/" that is an existing directory) wins over a session of the same name; a bare
    name is a session name; anything else is left as given (a pane id or a herdr agent name). `herdr-api agent list`
    is called only when the argument is a path or a session name."""
    is_directory = names_a_directory(arg)
    row = None if is_directory else session_registry.row_for_name(arg)
    if not is_directory and row is None:
        return resolved(arg, VIA_AS_GIVEN)

    try:
        agents = claude_agents()
    except PaneCallError as error:
        print(str(error), file=sys.stderr)
        return EXIT_TOOL_FAILED
    if is_directory:
        return resolve_path(arg, agents)
    return resolve_session(row, arg, agents)


def main(argv):
    if argv[1:] == ["sender"]:
        return sender()
    if len(argv) == 3 and argv[1] == "resolve":
        return resolve(argv[2])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
