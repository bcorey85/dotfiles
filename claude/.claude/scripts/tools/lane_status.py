#!/usr/bin/env python3
"""lane_status.py: print what needs attention: low memory, low or crowded scratch space, and each open lane whose
claude agent is not working.

Usage: lane_status.py

Lines, one per problem:
  <name>: no agent                 no claude agent runs inside the lane's worktree
  <name>: <status>                 the lane's agent has a status other than working
  <name>: worktree gone            the lane file's worktree folder is missing
  memory: <N.N> GB available, under <T> GB
  memory: cannot read              memory could not be read on this system
  scratch: <N.N> GB free on <dir>, under <T> GB
  scratch: <root> holds <N.N> GB, over <C> GB

Environment: LANE_STATUS_MIN_MEMORY_GB (8), LANE_STATUS_MIN_SCRATCH_GB (1), LANE_STATUS_SCRATCH_CAP_GB (4).
Exit 0 with nothing printed, 1 when something is printed, 2 on a bad lane file, a bad threshold, or a failed
herdr-api, df or du call (the message is on stderr)."""
import math
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hook_input
import lane_entries
import script_utils
import session_pane
import system_resources

EXIT_PROBLEMS = 1
EXIT_FAILED = 2
WORKING_STATUS = "working"
DEFAULT_THRESHOLDS_GB = {
    "LANE_STATUS_MIN_MEMORY_GB": 8,
    "LANE_STATUS_MIN_SCRATCH_GB": 1,
    "LANE_STATUS_SCRATCH_CAP_GB": 4,
}


class StatusError(Exception):
    """Something this tool needs could not be read; the message names it."""


def threshold_gb(variable):
    """The number of GB the environment variable holds, or its default. Raises StatusError naming the variable."""
    text = os.environ.get(variable, "")
    if text == "":
        return DEFAULT_THRESHOLDS_GB[variable]
    try:
        value = float(text)
    except ValueError as error:
        raise StatusError(f"{variable}={text}: expected a number of GB") from error
    if not math.isfinite(value) or value < 0:
        raise StatusError(f"{variable}={text}: expected a number of GB, 0 or more")
    return value


def memory_lines(minimum):
    available = system_resources.memory_available_gb()
    if available is None:
        return ["memory: cannot read"]

    if available >= minimum:
        return []
    return [f"memory: {available:.1f} GB available, under {minimum:g} GB"]


def scratch_lines(minimum, cap):
    root = hook_input.claude_code_temp_root()
    lines = []

    folder = script_utils.nearest_existing_folder(root)
    free = system_resources.free_gb(folder)
    if free < minimum:
        lines.append(f"scratch: {free:.1f} GB free on {folder}, under {minimum:g} GB")

    if not os.path.isdir(root):
        return lines

    held = system_resources.tree_gb(root)
    if held > cap:
        lines.append(f"scratch: {root} holds {held:.1f} GB, over {cap:g} GB")
    return lines


def lane_line(lane, agents):
    """The line for one lane, or None when its agent is working."""
    name = lane["name"]
    if not os.path.isdir(lane["worktree"]):
        return f"{name}: worktree gone"

    inside = session_pane.agents_in(lane["worktree"], agents)
    if not inside:
        return f"{name}: no agent"

    statuses = [agent.get("agent_status") or "unknown" for agent in inside]
    if WORKING_STATUS in statuses:
        return None
    return f"{name}: {statuses[0]}"


def lane_lines():
    try:
        lanes = lane_entries.all_entries()
    except lane_entries.LaneFileError as error:
        raise StatusError(str(error)) from error

    if not lanes:
        return []

    agents = session_pane.claude_agents()
    lines = [lane_line(lane, agents) for lane in lanes]
    return [line for line in lines if line is not None]


def main(argv):
    if len(argv) > 1:
        print(__doc__, file=sys.stderr)
        return EXIT_FAILED

    try:
        minimum_memory = threshold_gb("LANE_STATUS_MIN_MEMORY_GB")
        minimum_scratch = threshold_gb("LANE_STATUS_MIN_SCRATCH_GB")
        scratch_cap = threshold_gb("LANE_STATUS_SCRATCH_CAP_GB")
        lines = memory_lines(minimum_memory) + scratch_lines(minimum_scratch, scratch_cap) + lane_lines()
    except (StatusError, system_resources.ResourceReadError, session_pane.PaneCallError) as error:
        print(f"lane_status: {error}", file=sys.stderr)
        return EXIT_FAILED

    for line in lines:
        print(line)
    return EXIT_PROBLEMS if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
