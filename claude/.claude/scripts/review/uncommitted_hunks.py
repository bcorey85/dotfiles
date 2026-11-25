"""The uncommitted change in a repo, as one line per changed run, so a stop that leaves the tree dirty says what is
dirty. `hunk_lines` reads git only; `stop_lines` finds the repo through `review_fix_asks.packet_repo` (the launch
record's `--repo`, else the session's repo)."""

import pathlib
import sys
import typing

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import git_raw_diff
import script_utils
from capped_review import CAP_REACHED
from diff_ranges import changed_ranges, range_line
from review_fix_asks import missing_packet_repo_reason, packet_repo

NO_CHANGE_LINE = "no uncommitted change"
NOT_READ_LINE = "not read: a git call failed"
STOP_PREFIX = "Uncommitted: "


class RawChanges(typing.NamedTuple):
    """The tracked paths git shows changed against HEAD, by kind."""

    changed: set
    deleted: set
    submodules: set


def parse_raw_changes(raw_text):
    """RawChanges of the `git diff --raw -z` output `raw_text`; a rename or copy counts by its new path, and a path
    with mode 160000 is a submodule."""
    changes = RawChanges(set(), set(), set())
    # With -z each entry is a ":<old mode> <new mode> <old sha> <new sha> <status>" field, then its path, and a
    # second path (the new one) for a rename or copy.
    for entry in git_raw_diff.raw_entries(raw_text):
        name = entry.path
        changes.changed.add(name)
        if entry.status[0] == "D":
            changes.deleted.add(name)
        elif git_raw_diff.SUBMODULE_MODE in (entry.old_mode, entry.new_mode):
            changes.submodules.add(name)
    return changes


def hunk_lines(repo):
    """Lines naming the uncommitted change of `repo` against HEAD: one `path:first-last` (or `path:N`) per run of
    changed lines, `path (changed)` per tracked file git shows changed with no line run (a binary file, a mode change
    or a pure rename), per changed submodule, or whose name git quotes in the diff header, `path (deleted)` per
    deleted tracked file, `path (untracked)` per untracked file. One "no uncommitted change" line for a clean tree;
    one "not read" line when a git call fails."""
    # The prefixes and textconv are pinned so the user's git config cannot change the path keys or line numbers.
    diff_text = script_utils.git_output(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-color",
                                        "--src-prefix=a/", "--dst-prefix=b/", "--relative", "HEAD")
    raw_text = script_utils.git_output(repo, "diff", "--raw", "-z", "--relative", "HEAD")
    untracked = script_utils.untracked_paths(repo)
    if None in (diff_text, raw_text, untracked):
        return [NOT_READ_LINE]
    raw = parse_raw_changes(raw_text)
    lines = []
    paths_with_runs = set()
    for path, runs in changed_ranges(diff_text).items():
        # Git C-quotes a path with a quote, backslash or control byte in the diff header, so its key never matches the
        # raw name of the `-z` list. That path falls through to its `(changed)` line below; `/dev/null` is never listed.
        # A submodule's "Subproject commit" lines are no line edit, so it gets no run either.
        if path not in raw.changed or path in raw.submodules:
            continue
        if runs:
            paths_with_runs.add(path)
        lines += [range_line(path, first, last) for first, last in runs]
    for path in sorted(raw.changed - paths_with_runs - raw.deleted):
        lines.append(f"{path} (changed)")
    lines += [f"{path} (deleted)" for path in sorted(raw.deleted)]
    lines += [f"{path} (untracked)" for path in untracked]
    return lines or [NO_CHANGE_LINE]


def stop_lines(state):
    """`hunk_lines` of the packet's repo (`packet_repo` of the state's launch record), for a stop that leaves the tree
    dirty, each behind `STOP_PREFIX` so a caller does not copy one into a handoff. When the packet names no repo, one
    "not read" line with the reason."""
    relaunch_args = state.get("relaunch_args") or []
    repo = packet_repo(relaunch_args)
    if repo is None:
        return [f"{STOP_PREFIX}not read: {missing_packet_repo_reason(relaunch_args)}"]
    return [f"{STOP_PREFIX}{line}" for line in hunk_lines(repo)]


def cap_stop_lines(packet, state):
    """`stop_lines` for a cap-reached packet only; [] for any other status, whose stops print no hunk lines."""
    if packet["status"] != CAP_REACHED:
        return []
    return stop_lines(state)
