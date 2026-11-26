"""A stop that leaves the tree dirty says what is dirty: `stop_lines` finds the repo through
`review_fix_asks.packet_repo` (the launch record's `--repo`, else the session's repo) and reads it with
`uncommitted_change.hunk_lines`."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import uncommitted_change
from capped_review import CAP_REACHED
from review_fix_asks import missing_packet_repo_reason, packet_repo

STOP_PREFIX = "Uncommitted: "


def stop_lines(state):
    """The hunk lines of the packet's repo (`packet_repo` of the state's launch record), for a stop that leaves the
    tree dirty, each behind `STOP_PREFIX` so a caller does not copy one into a handoff. When the packet names no repo,
    one "not read" line with the reason."""
    relaunch_args = state.get("relaunch_args") or []
    repo = packet_repo(relaunch_args)
    if repo is None:
        return [f"{STOP_PREFIX}not read: {missing_packet_repo_reason(relaunch_args)}"]
    return [f"{STOP_PREFIX}{line}" for line in uncommitted_change.hunk_lines(repo)]


def cap_stop_lines(packet, state):
    """`stop_lines` for a cap-reached packet only; [] for any other status, whose stops print no hunk lines."""
    if packet["status"] != CAP_REACHED:
        return []
    return stop_lines(state)
