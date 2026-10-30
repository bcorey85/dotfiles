"""How much of a change a later edit has removed: the lines a change adds, and how many of them the tree still holds.

A line counts by its text with surrounding whitespace dropped, and blank lines never count. A line that is removed
and added back unchanged is not removed, because the count compares the added lines with the tree as it is now.
"""

from collections import Counter

# A loop stops when the passes removed at least this share of the added lines, and the change added at least
# MIN_ADDED_LINES of them.
REMOVED_SHARE = 0.5
MIN_ADDED_LINES = 10


def nonblank_lines(text):
    return Counter(line.strip() for line in text.splitlines() if line.strip())


def added_lines(old_text, new_text):
    """The lines new_text holds that old_text does not, as a Counter of line text: a line repeated in both texts
    counts only for the copies the change added."""
    return nonblank_lines(new_text) - nonblank_lines(old_text)


def removed_by_file(added_by_file, current_added_by_file):
    """{path: lines removed} for each file that lost some of its added lines. `added_by_file` is {path: Counter}
    from added_lines; `current_added_by_file` is the same map for the source additions the tree holds over HEAD now,
    and a path it lacks added nothing. A line counts as kept when any file adds it now, so a move into another file
    is not a removal, and a line HEAD already holds is not kept by that copy.
    Each kept copy is used up, so one surviving copy keeps the line for one file only."""
    current_lines = sum(current_added_by_file.values(), Counter())

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
