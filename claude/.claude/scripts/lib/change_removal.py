"""How much of a change a later edit has removed: the lines a change adds, and how many of them the tree still holds.

A line counts by its text with surrounding whitespace dropped, and blank lines never count. A line that is removed
and added back unchanged is not removed, because the count compares the added lines with the tree as it is now.
A hunk whose only change is formatting (whitespace, line breaks, quote style, a trailing comma before a closing
bracket) adds no lines, so reverting formatter churn is not removed work.
"""

from collections import Counter

import source_text

# A loop stops when the passes removed at least this share of the added lines, and the change added at least
# MIN_ADDED_LINES of them.
REMOVED_SHARE = 0.5
MIN_ADDED_LINES = 10


def nonblank_lines(text):
    return Counter(source_text.stripped_lines(text))


def added_lines(old_text, new_text, path=None):
    """The lines new_text holds that old_text does not, as a Counter of line text: a line repeated in both texts
    counts only for the copies the change added. Formatting-only hunks add nothing (see the module docstring).
    `path` is the file's path, which tells whether a one-comma group is a tuple."""
    reformatted = source_text.formatting_only_lines(old_text, new_text, path)
    new_counts = nonblank_lines(new_text) - reformatted.new
    old_counts = nonblank_lines(old_text) - reformatted.old
    return new_counts - old_counts


def removed_by_file(added_by_file, current_added_by_file, fix_added_by_file=None):
    """{path: lines removed} for each file that lost some of its added lines. `added_by_file` is {path: Counter}
    from added_lines; `current_added_by_file` is the same map for the source additions the tree holds over HEAD now,
    and a path it lacks added nothing. A line counts as kept when any file adds it now, so a move into another file
    is not a removal, and a line HEAD already holds is not kept by that copy.
    `fix_added_by_file` is the same map for what the fix passes added over the tree the loop started from: a line a
    pass added to any file counts as kept even when HEAD already held a copy there, so a move into a file that
    holds the same line is not a removal.
    Each kept copy is used up, so one surviving copy keeps the line for one file only. The two maps measure a file
    against different bases, so they merge per file (one copy keeps one line per file); copies in different files
    add up."""
    fix_by_file = fix_added_by_file or {}
    current_lines = Counter()
    for path in current_added_by_file.keys() | fix_by_file.keys():
        current_lines += current_added_by_file.get(path, Counter()) | fix_by_file.get(path, Counter())

    removed = {}
    for path, added in added_by_file.items():
        kept = added & current_lines
        current_lines -= kept
        lost = sum(added.values()) - sum(kept.values())
        if lost:
            removed[path] = lost
    return removed


def is_gutted(added_by_file, removed):
    """Whether `removed` ({path: lines}) is at least REMOVED_SHARE of the added lines, of a change that added at least
    MIN_ADDED_LINES."""
    total = sum(sum(added.values()) for added in added_by_file.values())
    return total >= MIN_ADDED_LINES and sum(removed.values()) >= total * REMOVED_SHARE


def removal_blocker(added_by_file, removed):
    """The blocker line for a gutted change: the counts, and the files that lost the most (up to three)."""
    total = sum(sum(added.values()) for added in added_by_file.values())
    lost = sum(removed.values())
    worst = sorted(removed, key=lambda path: (-removed[path], path))[:3]
    files = ", ".join(f"{path} ({removed[path]})" for path in worst)
    return (f"the fix passes removed {lost} of the {total} source lines the change under review adds; "
            f"most lost in {files}")
