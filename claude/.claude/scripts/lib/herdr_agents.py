"""The agents herdr reports: `herdr-api agent list` read as plain dicts, and which of them run inside a folder.

Standard library and script_utils only."""
import json
import os
import subprocess

import script_utils

AGENT_LIST_CALL = "herdr-api agent list"


class PaneCallError(Exception):
    """The herdr-api call failed; the message names the call."""


def herdr_reply(words):
    """The JSON object `herdr-api <words>` prints. Raises PaneCallError, naming the call, when herdr-api is missing,
    exits non-zero or prints no JSON object."""
    call = "herdr-api " + " ".join(words)
    try:
        finished = subprocess.run(["herdr-api", *words], capture_output=True, text=True)
    except OSError as error:
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
