#!/usr/bin/env python3
"""lane_status.py: print what needs attention: low memory, low or crowded scratch space, each live diff viewer over its
memory cap, and each open lane whose claude agent is not working.

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
  viewer <lane, folder or pane>: <size>, over <cap> cap (pane <pane>, pid <pid>)
                                   a live hunk diff viewer holds more memory than its cap
  viewers: cannot read (<reason>)  the viewer list or a viewer's process could not be read

--changes prints only the lines that changed since the last --changes run (a viewer line counts as changed only
when its pane or pid does, not its size), and `<name>: working` for a lane that was reported before and now
works. It keeps the last run's lines in `${XDG_STATE_HOME:-~/.local/state}/lane-status/seen.json`.

Environment: LANE_STATUS_MIN_MEMORY_GB (8), LANE_STATUS_MIN_SCRATCH_GB (1), LANE_STATUS_SCRATCH_CAP_GB (4). The
viewer cap is read from `hunk-review-pane --viewers`, which takes it from HUNK_REVIEW_MEMORY_MAX (1G).
Exit 0 with nothing printed, 1 when something is printed, 2 on a bad lane file, a bad threshold, or a failed
herdr-api, df or du call (the message is on stderr)."""
import json
import math
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import api_error_stop
import herdr_agents
import hook_input
import lane_entries
import loop_transcript
import process_group
import script_utils
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
VIEWER_PROGRAM = "hunk"
VIEWER_LAUNCHER = "hunk-review-pane"
VIEWER_KEY_PREFIX = "viewer:"
VIEWERS_KEY = "viewers:"
MEMORY_KEY = "memory:"
SCRATCH_KEY = "scratch:"


class StatusError(Exception):
    """Something this tool needs could not be read; the message names it."""


class ViewerReadError(Exception):
    """The viewer list could not be read or is not in the expected shape; the message says why."""


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


def check_viewer_shape(listing):
    """Raises ViewerReadError unless `listing` is {cap_bytes: int, viewers: [{pane: str, root: str, pid: int}]}."""
    if not isinstance(listing, dict) or not script_utils.is_int(listing.get("cap_bytes")):
        raise ViewerReadError("cap_bytes is missing or not an integer")
    viewers = listing.get("viewers")
    if not isinstance(viewers, list):
        raise ViewerReadError("viewers is not a list")
    for row in viewers:
        if not isinstance(row, dict):
            raise ViewerReadError(f"viewer row is not an object: {row!r}")
        if not isinstance(row.get("pane"), str) or not isinstance(row.get("root"), str) \
                or not script_utils.is_int(row.get("pid")):
            raise ViewerReadError(f"viewer row needs a str pane, a str root and an int pid: {row!r}")


def read_viewers():
    """The checked JSON of `hunk-review-pane --viewers`. Raises ViewerReadError."""
    launcher = shutil.which(VIEWER_LAUNCHER)
    if launcher is None:
        raise ViewerReadError(f"{VIEWER_LAUNCHER} is not on PATH")
    finished = script_utils.run_or_raise([launcher, "--viewers"], ViewerReadError, check=True)
    try:
        listing = json.loads(finished.stdout)
    except ValueError as error:
        raise ViewerReadError(f"{VIEWER_LAUNCHER} --viewers printed invalid JSON: {error}") from error
    check_viewer_shape(listing)
    return listing


def viewer_name(row):
    """The lane that holds the viewer's root, else the root, else the pane."""
    if row["root"]:
        try:
            lane = lane_entries.entry_containing(row["root"])
        except lane_entries.LaneFileError as error:
            raise StatusError(str(error)) from error
        if lane is not None:
            return lane["name"]
        return row["root"]
    return row["pane"]


def oversized_viewer(row, cap):
    """{line, pane, pid} for one viewer row, or None when its process is gone, is another program, or is within the
    cap. The line carries the live size; `pane` and `pid` say which viewer it is."""
    pid = row["pid"]
    if not process_group.pid_is_alive(pid):
        return None
    if process_group.program_name(pid) != VIEWER_PROGRAM:
        return None
    size = process_group.resident_bytes(pid)
    if size is None or size <= cap:
        return None
    size_label = system_resources.size_text(size)
    cap_label = system_resources.size_text(cap)
    line = f"viewer {viewer_name(row)}: {size_label}, over {cap_label} cap (pane {row['pane']}, pid {pid})"
    return {"line": line, "pane": row["pane"], "pid": pid}


def viewer_report():
    """{`viewer:<pane>`: {line, pane, pid}} for each oversized viewer, plus {`viewers:`: the cannot-read line} when
    the list or any viewer's process could not be read; the other viewers still report."""
    try:
        listing = read_viewers()
    except ViewerReadError as error:
        return {VIEWERS_KEY: f"viewers: cannot read ({error})"}
    report = {}
    for row in listing["viewers"]:
        try:
            viewer = oversized_viewer(row, listing["cap_bytes"])
        except process_group.ProcessQueryError as error:
            report[VIEWERS_KEY] = f"viewers: cannot read ({error})"
            continue
        if viewer is not None:
            report[f"{VIEWER_KEY_PREFIX}{row['pane']}"] = viewer
    return report


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
    transcript = api_error_stop.agent_transcript(agent)
    if transcript is None:
        return f"{name}: {status}"

    error_record = api_error_stop.last_api_error(transcript)
    if error_record is not None:
        return f"{name}: dead ({api_error_stop.error_reason(error_record)})"

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
    """The lines the last --changes run printed or held, keyed by lane name, by `memory:` and `scratch:`, by
    `viewer:<pane>` for an oversized viewer and by `viewers:` for the viewer cannot-read line; {} when there was no
    earlier run or its file is unreadable."""
    try:
        seen = json.loads(seen_file().read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"lane_status: could not read {seen_file()}, starting fresh: {error}", file=sys.stderr)
        return {}
    return seen if isinstance(seen, dict) else {}


def line_text(value):
    """The text a report value prints: a viewer value is {line, pane, pid}, every other value is the line itself."""
    if isinstance(value, dict):
        return value["line"]
    return value


def change_identity(value):
    """What --changes compares: a viewer is its pane and pid, so its growing size does not read as a change."""
    if isinstance(value, dict):
        return {"pane": value["pane"], "pid": value["pid"]}
    return value


def changed_lines(current, seen):
    """The lines of `current` whose `change_identity` differs from `seen`, plus
    `<name>: working` for a lane `seen` held a line for and whose agent now works. A lane absent from `current`
    (closed) prints nothing."""
    lines = []
    for key, value in current.items():
        before = seen.get(key)
        if change_identity(value) == change_identity(before):
            continue
        if value is None and before is not None:
            label = key.removesuffix(":")
            lines.append(f"{label}: working")
        elif value is not None:
            lines.append(line_text(value))
    return lines


def machine_report(minimum_memory, minimum_scratch, scratch_cap):
    """{`memory:` or `scratch:`: the joined lines, or None when that resource is fine}."""
    memory = memory_lines(minimum_memory)
    scratch = scratch_lines(minimum_scratch, scratch_cap)
    return {MEMORY_KEY: "\n".join(memory) or None, SCRATCH_KEY: "\n".join(scratch) or None}


def current_report():
    minimum_memory = threshold_gb("LANE_STATUS_MIN_MEMORY_GB")
    minimum_scratch = threshold_gb("LANE_STATUS_MIN_SCRATCH_GB")
    scratch_cap = threshold_gb("LANE_STATUS_SCRATCH_CAP_GB")
    report = machine_report(minimum_memory, minimum_scratch, scratch_cap)
    report.update(viewer_report())

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
        lines = [line_text(value) for value in report.values() if value is not None]

    for line in lines:
        print(line)
    return EXIT_PROBLEMS if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
