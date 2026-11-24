#!/usr/bin/env python3
"""lane_status.py: print what needs attention: low memory, low or crowded scratch space, and each open lane whose
claude agent is not working.

Usage: lane_status.py [--changes]

Lines, one per problem:
  <name>: <status>                 the lane's agent has a status other than working and no open background work
  <name>: waiting on <N> background job(s)
                                   the lane's agent is not working, and its transcript holds background shells or
                                   subagents that have not reported back
  <name>: dead (no agent)          no claude agent runs inside the lane's worktree (workspace closed, killed)
  <name>: dead (worktree gone)     the lane file's worktree folder is missing
  <name>: dead (login expired)     the agent's transcript ends on an API error that asks for a login
  <name>: dead (api error)         the agent's transcript ends on any other API error
  memory: <N.N> GB available, under <T> GB
  memory: cannot read              memory could not be read on this system
  scratch: <N.N> GB free on <dir>, under <T> GB
  scratch: <root> holds <N.N> GB, over <C> GB

--changes prints only the lines that differ from the last --changes run, and `<name>: working` for a lane that was
reported before and now works. It keeps the last run's lines in
`${XDG_STATE_HOME:-~/.local/state}/lane-status/seen.json`; a relative `XDG_STATE_HOME` is ignored.

Environment: LANE_STATUS_MIN_MEMORY_GB (8), LANE_STATUS_MIN_SCRATCH_GB (1), LANE_STATUS_SCRATCH_CAP_GB (4).
Exit 0 with nothing printed, 1 when something is printed, 2 on a bad lane file, a bad threshold, or a failed
herdr-api, df or du call (the message is on stderr)."""
import json
import math
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import herdr_agents
import hook_input
import lane_entries
import loop_transcript
import script_utils
import session_registry
import system_resources

EXIT_PROBLEMS = 1
EXIT_FAILED = 2
WORKING_STATUS = "working"
CHANGES_FLAG = "--changes"
DEFAULT_THRESHOLDS_GB = {
    "LANE_STATUS_MIN_MEMORY_GB": 8,
    "LANE_STATUS_MIN_SCRATCH_GB": 1,
    "LANE_STATUS_SCRATCH_CAP_GB": 4,
}
# Words in an API error record that mean the session lost its login and will not go on until someone logs in.
LOGIN_WORDS = ("/login", "401", "authentication", "oauth token")


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


def transcript_of(agent):
    """The transcript path of the agent's session, or None when herdr names no session or no transcript matches."""
    agent_session = agent.get("agent_session")
    session_id = agent_session.get("value") if isinstance(agent_session, dict) else None
    if not isinstance(session_id, str) or not session_id:
        return None

    found = sorted(session_registry.projects_dir().glob(f"*/{session_id}.jsonl"))
    if not found:
        return None
    return found[0]


def api_error_reason(transcript):
    """`login expired` or `api error` when the transcript ends on an API error record, else None."""
    record = script_utils.last_transcript_record(transcript)
    if record is None or record.get("isApiErrorMessage") is not True:
        return None

    text = json.dumps(record.get("message") or {}).lower()
    if any(word in text for word in LOGIN_WORDS):
        return "login expired"
    return "api error"


def open_background_jobs(transcript):
    """The count of background shells and subagents the transcript launched that have not reported back."""
    try:
        return loop_transcript.LoopTranscript(transcript).open_dispatches()
    except (OSError, ValueError) as error:
        # An unreadable or torn transcript leaves the plain status: the pane state is still true.
        print(f"lane_status: could not read {transcript}: {error}", file=sys.stderr)
        return 0


def idle_line(name, agent):
    """The line for a lane whose agent is not working: dead on an API error, waiting on open background work, or
    the plain status."""
    status = agent.get("agent_status") or "unknown"
    transcript = transcript_of(agent)
    if transcript is None:
        return f"{name}: {status}"

    reason = api_error_reason(transcript)
    if reason is not None:
        return f"{name}: dead ({reason})"

    jobs = open_background_jobs(transcript)
    if jobs:
        return f"{name}: waiting on {jobs} background job(s)"
    return f"{name}: {status}"


def lane_line(lane, agents):
    """The line for one lane, or None when its agent is working."""
    name = lane["name"]
    if not os.path.isdir(lane["worktree"]):
        return f"{name}: dead (worktree gone)"

    inside = herdr_agents.agents_in(lane["worktree"], agents)
    if not inside:
        return f"{name}: dead (no agent)"

    statuses = [agent.get("agent_status") or "unknown" for agent in inside]
    if WORKING_STATUS in statuses:
        return None
    return idle_line(name, inside[0])


def lane_report(lanes, agents):
    """{lane name: its line, or None when its agent is working}."""
    return {lane["name"]: lane_line(lane, agents) for lane in lanes}


def read_lanes():
    try:
        return lane_entries.all_entries()
    except lane_entries.LaneFileError as error:
        raise StatusError(str(error)) from error


def seen_file():
    return script_utils.xdg_state_home() / "lane-status" / "seen.json"


def read_seen():
    """The lines the last --changes run printed or held, keyed by lane name or by `memory` and `scratch`; {} when
    there was no earlier run or its file is unreadable."""
    try:
        seen = json.loads(seen_file().read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"lane_status: could not read {seen_file()}, starting fresh: {error}", file=sys.stderr)
        return {}
    return seen if isinstance(seen, dict) else {}


def changed_lines(current, seen):
    """The lines of `current` that differ from `seen`, plus `<name>: working` for a lane `seen` held a line for and
    whose agent now works. A lane absent from `current` (closed) prints nothing."""
    lines = []
    for key, line in current.items():
        before = seen.get(key)
        if line == before:
            continue
        if line is None and before is not None:
            lines.append(f"{key}: working")
        elif line is not None:
            lines.append(line)
    return lines


def machine_report(minimum_memory, minimum_scratch, scratch_cap):
    """{`memory` or `scratch`: the joined lines, or None when that resource is fine}."""
    memory = memory_lines(minimum_memory)
    scratch = scratch_lines(minimum_scratch, scratch_cap)
    return {"memory": "\n".join(memory) or None, "scratch": "\n".join(scratch) or None}


def current_report():
    minimum_memory = threshold_gb("LANE_STATUS_MIN_MEMORY_GB")
    minimum_scratch = threshold_gb("LANE_STATUS_MIN_SCRATCH_GB")
    scratch_cap = threshold_gb("LANE_STATUS_SCRATCH_CAP_GB")
    report = machine_report(minimum_memory, minimum_scratch, scratch_cap)

    lanes = read_lanes()
    if not lanes:
        return report
    agents = herdr_agents.claude_agents()
    report.update(lane_report(lanes, agents))
    return report


def main(argv):
    arguments = argv[1:]
    if arguments not in ([], [CHANGES_FLAG]):
        print(__doc__, file=sys.stderr)
        return EXIT_FAILED

    try:
        report = current_report()
    except (StatusError, system_resources.ResourceReadError, herdr_agents.PaneCallError) as error:
        print(f"lane_status: {error}", file=sys.stderr)
        return EXIT_FAILED

    if arguments:
        lines = changed_lines(report, read_seen())
        seen_file().parent.mkdir(parents=True, exist_ok=True)
        script_utils.write_text_atomically(seen_file(), json.dumps(report))
    else:
        lines = [line for line in report.values() if line is not None]

    for line in lines:
        print(line)
    return EXIT_PROBLEMS if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
