"""The lane list: one reader of `lanes.py list`, shared by herdr-lane-sweep and herdr-worktree-prune.

The path of lanes.py comes from toolkit-tools.bash, the one owner of its default and of HERDR_LANES_CLI.
"""
import json
import pathlib
import subprocess
import sys

TOOLS_FILE = pathlib.Path(__file__).resolve().parent / "toolkit-tools.bash"


class LaneListError(Exception):
    """The lane list cannot be read; the message says why."""


def lanes_cli_path(timeout):
    """The path of lanes.py, as toolkit-tools.bash sets `lanes_cli`."""
    command = ["bash", "-c", '. "$1"; printf %s "$lanes_cli"', "_", str(TOOLS_FILE)]
    try:
        finished = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneListError(f"cannot read lanes_cli from {TOOLS_FILE}: {error}") from error
    if finished.returncode != 0 or not finished.stdout:
        raise LaneListError(f"cannot read lanes_cli from {TOOLS_FILE}: {finished.stderr.strip() or 'empty'}")
    return finished.stdout


def read_lane_entries(timeout):
    """The entries of `lanes.py list`, each a dict. Raises LaneListError when the list cannot be read."""
    command = [sys.executable, lanes_cli_path(timeout), "list"]
    try:
        asked = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        raise LaneListError(f"lanes list did not run: {error}") from error
    if asked.returncode != 0:
        raise LaneListError(f"lanes list failed: {asked.stderr.strip() or asked.returncode}")
    try:
        return json.loads(asked.stdout)["lanes"]
    except (ValueError, KeyError, TypeError) as error:
        raise LaneListError(f"lanes list has an unexpected answer: {error!r}") from error
