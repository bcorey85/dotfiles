"""The new-side line ranges that a unified diff changes, and a test of whether a line falls inside them. It takes plain
diff text with any amount of context and any file prefix (`b/path`, or a bare path), and knows no repo or table."""

import re

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NEW_FILE_HEADER = re.compile(r"^\+\+\+ (?:b/)?(.+?)(?:\t.*)?$")
# Lines either side of a changed run that still count as inside it.
RANGE_SLACK = 3


def hunk_runs(body, first_new_line):
    """[(first, last)] of the changes in one hunk body (its lines after the `@@` header), whose first new-side line is
    `first_new_line`. Raises ValueError on a body line that starts with none of '-', '+', ' ' or '\\'."""
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
            runs.append((run_start, max(run_start, new_number - 1)))
            run_start = None
        new_number += 1
    if run_start is not None:
        runs.append((run_start, max(run_start, new_number - 1)))
    return runs


def changed_ranges(diff_text):
    """{path: [(first, last)]} of the new-side lines that the diff changes, in order. A run of added lines is its first
    to its last line; a run of removed lines with none added is the one line where they were. Context lines are not
    changes. The hunk header's counts say where each body ends, so a removed line that starts with '-- ' is no file
    header. Raises ValueError on a hunk body line the grammar does not parse."""
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
        current.extend(hunk_runs(body, first_new_line))
    return ranges


def in_ranges(ranges, line, slack=RANGE_SLACK):
    """True when `line` is within `slack` lines of any (first, last) range."""
    return any(first - slack <= line <= last + slack for first, last in ranges)
