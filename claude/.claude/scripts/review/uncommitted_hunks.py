"""The uncommitted change in a repo, as one line per changed run, so a stop that leaves the tree dirty says what is
dirty. `hunk_lines` reads git only; `stop_lines` finds the repo through `review_fix_asks.packet_repo` (the launch
record's `--repo`, else the session's repo)."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import script_utils
from diff_ranges import changed_ranges, range_line
from review_fix_asks import missing_packet_repo_reason, packet_repo

NO_CHANGE_LINE = "no uncommitted change"
NOT_READ_LINE = "not read: a git call failed"
STOP_PREFIX = "Uncommitted: "


def hunk_lines(repo):
    """Lines naming the uncommitted change of `repo` against HEAD: one `path:first-last` (or `path:N`) per run of
    changed lines, `path (changed)` per tracked file git shows changed with no line run (a binary file, a mode change
    or a pure rename) or whose name git quotes in the diff header, `path (deleted)` per deleted tracked file,
    `path (untracked)` per untracked file. One "no uncommitted change" line for a clean tree; one "not read" line
    when a git call fails."""
    # The prefixes and textconv are pinned so the user's git config cannot change the path keys or line numbers.
    diff_text = script_utils.git_output(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-color",
                                        "--src-prefix=a/", "--dst-prefix=b/", "--relative", "HEAD")
    changed_text = script_utils.git_output(repo, "diff", "--name-only", "-z", "--relative", "HEAD")
    deleted_text = script_utils.git_output(repo, "diff", "--name-only", "-z", "--relative", "--diff-filter=D", "HEAD")
    untracked = script_utils.untracked_paths(repo)
    if None in (diff_text, changed_text, deleted_text, untracked):
        return [NOT_READ_LINE]
    lines = []
    paths_with_runs = set()
    deleted = {name for name in deleted_text.split("\0") if name}
    changed = {name for name in changed_text.split("\0") if name}
    for path, runs in changed_ranges(diff_text).items():
        # Git C-quotes a path with a quote, backslash or control byte in the diff header, so its key never matches the
        # raw name of the `-z` list. That path falls through to its `(changed)` line below; `/dev/null` is never listed.
        if path not in changed:
            continue
        if runs:
            paths_with_runs.add(path)
        lines += [range_line(path, first, last) for first, last in runs]
    for path in sorted(changed - paths_with_runs - deleted):
        lines.append(f"{path} (changed)")
    lines += [f"{path} (deleted)" for path in sorted(deleted)]
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
