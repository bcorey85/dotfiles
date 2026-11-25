"""The new-side line ranges that a unified diff changes, a test of whether a line falls inside them, and the
`path:first-last` text of one range. It takes plain
diff text with any amount of context and any file prefix (`b/path`, or a bare path), and knows no repo or table."""

import re

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NEW_FILE_HEADER = re.compile(r"^\+\+\+ (?:b/)?(.+?)(?:\t.*)?$")
# Lines either side of a changed run that still count as inside it.
RANGE_SLACK = 3


def hunk_runs(body, first_new_line, added_only=False):
    """[(first, last)] of the changes in one hunk body (its lines after the `@@` header), whose first new-side line is
    `first_new_line`. With `added_only`, a run that adds no line is left out. Raises ValueError on a body line that
    starts with none of '-', '+', ' ' or '\\'."""
    runs = []
    new_number = first_new_line
    run_start = None
    for line in body:
        marker = line[:1]
        if marker == "\\":
            continue
        if marker in ("+", "-"):
            run_start = new_number if run_start is None else run_start
            new_number += marker == "+"
            continue
        if marker not in (" ", ""):
            raise ValueError(f"expected a hunk body line that starts with '-', '+', ' ' or '\\'; got {line!r}")
        if run_start is not None:
            runs += _closed_run(run_start, new_number, added_only)
            run_start = None
        new_number += 1
    if run_start is not None:
        runs += _closed_run(run_start, new_number, added_only)
    return runs


def _closed_run(run_start, next_new_line, added_only):
    """[(first, last)] of one run that started at new-side line `run_start` and ends before `next_new_line`; [] with
    `added_only` when the run added no line."""
    adds_a_line = next_new_line > run_start
    if added_only and not adds_a_line:
        return []
    return [(run_start, max(run_start, next_new_line - 1))]


def range_line(path, first, last):
    """`path:N` for a one-line run, `path:first-last` otherwise."""
    if first == last:
        return f"{path}:{first}"
    return f"{path}:{first}-{last}"


def added_ranges(diff_text):
    """{path: [(first, last)]} of the new-side lines that the diff adds: `changed_ranges` without the runs that only
    remove lines. A file the diff only removes lines from keeps its key, with no range."""
    return changed_ranges(diff_text, added_only=True)


def changed_ranges(diff_text, added_only=False):
    """{path: [(first, last)]} of the new-side lines that the diff changes, in order. A run of added lines is its first
    to its last line; a run of removed lines with none added is the one line where they were, or no range with
    `added_only`. Context lines are not changes. The hunk header's counts say where each body ends, so a removed line
    that starts with '-- ' is no file header. Raises ValueError on a hunk body line the grammar does not parse."""
    ranges = {}
    current = None
    lines = diff_text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        file_header = NEW_FILE_HEADER.match(line)
        if file_header:
            current = ranges.setdefault(file_header.group(1), [])
            continue
        header = HUNK_HEADER.match(line)
        if header is None or current is None:
            continue

        old_left = 1 if header.group(1) is None else int(header.group(1))
        new_left = 1 if header.group(3) is None else int(header.group(3))
        body = []
        while (old_left > 0 or new_left > 0) and index < len(lines):
            body_line = lines[index]
            index += 1
            body.append(body_line)
            marker = body_line[:1]
            if marker != "+" and marker != "\\":
                old_left -= 1
            if marker != "-" and marker != "\\":
                new_left -= 1
        # A hunk with no new-side lines names the line before the deletion.
        first_new_line = int(header.group(2)) + (header.group(3) == "0")
        current.extend(hunk_runs(body, first_new_line, added_only))
    return ranges


def in_ranges(ranges, line, slack=RANGE_SLACK):
    """True when `line` is within `slack` lines of any (first, last) range."""
    return any(first - slack <= line <= last + slack for first, last in ranges)
