"""The uncommitted change of a repo against HEAD, read from git only: one line per changed run, `path (changed)`,
`path (deleted)` or `path (untracked)` for a path with no line run, one clean line or one not-read line."""

import typing

import diff_ranges
import git_raw_diff
import script_utils

NO_CHANGE_LINE = "no uncommitted change"
NOT_READ_LINE = "not read: a git call failed"


class RawChanges(typing.NamedTuple):
    """The tracked paths git shows changed against HEAD, by kind."""

    changed: set
    deleted: set
    submodules: set


def parse_raw_changes(raw_text):
    """RawChanges of the `git diff --raw -z` output `raw_text`; a rename or copy counts by its new path, and a path
    with mode 160000 is a submodule."""
    changes = RawChanges(set(), set(), set())
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
    for path, runs in diff_ranges.changed_ranges(diff_text).items():
        # Git C-quotes a path with a quote, backslash or control byte in the diff header, so its key never matches the
        # raw name of the `-z` list. That path falls through to its `(changed)` line below; `/dev/null` is never listed.
        # A submodule's "Subproject commit" lines are no line edit, so it gets no run either.
        if path not in raw.changed or path in raw.submodules:
            continue
        if runs:
            paths_with_runs.add(path)
        lines += [diff_ranges.range_line(path, first, last) for first, last in runs]
    for path in sorted(raw.changed - paths_with_runs - raw.deleted):
        lines.append(f"{path} (changed)")
    lines += [f"{path} (deleted)" for path in sorted(raw.deleted)]
    lines += [f"{path} (untracked)" for path in untracked]
    return lines or [NO_CHANGE_LINE]
