"""The new-side line numbers a branch added, from parsed diff files and untracked files. Standard library only."""


def changed_line_sets(diff_files, untracked):
    """{path: set of new-side line numbers the branch added}, from parsed diff files (source_text.FileDiff) and the
    untracked entries (objects with `path` and `added_lines`), whose every line counts."""
    changed = {}
    for diff_file in diff_files:
        lines = changed.setdefault(diff_file.path, set())
        for hunk in diff_file.hunks:
            lines.update(number for number, _text in hunk.added)
    for entry in untracked:
        lines = changed.setdefault(entry.path, set())
        lines.update(number for number, _text in entry.added_lines)
    return changed


def range_touched(changed, path, first, last):
    """True when any line first..last of `path` is in the changed-line sets."""
    lines = changed.get(path, ())
    return any(number in lines for number in range(first, last + 1))


def range_added(changed, path, first, last):
    """True when every line first..last of `path` is in the changed-line sets."""
    lines = changed.get(path, ())
    return all(number in lines for number in range(first, last + 1))
