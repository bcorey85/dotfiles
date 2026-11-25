"""The agents herdr reports: `herdr-api agent list` read as plain dicts, which of them run inside a folder, and
the transcript of an agent's session.

Standard library, script_utils and session_registry only."""
import json
import os
import subprocess
import sys

import script_utils
import session_registry

AGENT_LIST_CALL = "herdr-api agent list"
# Seconds a herdr-api call may run before it counts as failed.
HERDR_CALL_TIMEOUT_SECONDS = 20


class PaneCallError(Exception):
    """The herdr-api call failed; the message names the call."""


def herdr_reply(words):
    """The JSON object `herdr-api <words>` prints. Raises PaneCallError, naming the call, when herdr-api is missing,
    exits non-zero, runs past the timeout or prints no JSON object."""
    call = "herdr-api " + " ".join(words)
    try:
        finished = subprocess.run(["herdr-api", *words], capture_output=True, text=True,
                                  timeout=HERDR_CALL_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PaneCallError(f"{call} failed: {error}") from error
    if finished.returncode != 0:
        raise PaneCallError(f"{call} failed with exit {finished.returncode}")

    try:
        reply = json.loads(finished.stdout)
    except ValueError as error:
        raise PaneCallError(f"{call} printed no JSON: {error}") from error
    if not isinstance(reply, dict):
        raise PaneCallError(f"{call} printed no JSON object")
    return reply


def listed_agents():
    """Every agent of `herdr-api agent list`. Raises PaneCallError when the call fails."""
    reply = herdr_reply(["agent", "list"])
    result = reply.get("result")
    agents = result.get("agents") if isinstance(result, dict) else None
    if not isinstance(agents, list):
        raise PaneCallError(f"{AGENT_LIST_CALL} printed no agents list")
    return [agent for agent in agents if isinstance(agent, dict)]


def claude_agents():
    """The claude agents of `herdr-api agent list`. Raises PaneCallError when the call fails."""
    return [agent for agent in listed_agents() if agent.get("agent") == "claude"]


def herdr_agent_session_id(agent):
    """The Claude session id herdr names for an agent, or None when it names none."""
    agent_session = agent.get("agent_session")
    session_id = agent_session.get("value") if isinstance(agent_session, dict) else None
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id


def herdr_agent_transcript(agent):
    """The transcript path of a herdr agent's session, or None when herdr names no session, no transcript matches, or
    several do (the stderr line names the session id and the count)."""
    session_id = herdr_agent_session_id(agent)
    if session_id is None:
        return None

    found = session_registry.session_transcripts(session_id)
    if not found:
        return None
    if len(found) > 1:
        print(f"herdr_agents: session {session_id} matches {len(found)} transcripts; reading none",
              file=sys.stderr)
        return None
    return found[0]


def agents_in(directory, agents):
    """The agents whose real cwd is inside the real path of `directory`; an agent whose cwd is missing or empty is
    not (an empty path would resolve to the caller's own folder)."""
    real_directory = os.path.realpath(directory)
    inside = []
    for agent in agents:
        cwd = agent.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            continue
        if script_utils.path_is_under(os.path.realpath(cwd), real_directory):
            inside.append(agent)
    return inside
