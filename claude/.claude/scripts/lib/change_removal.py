"""How much of a change a later edit has removed: the lines a change adds, and how many of them the tree still holds.

A line counts by its text with surrounding whitespace dropped, and blank lines never count. A line that is removed
and added back unchanged is not removed, because the count compares the added lines with the tree as it is now.
A hunk whose only change is formatting (whitespace, line breaks, quote style, a trailing comma before a closing
bracket) adds no lines, so reverting formatter churn is not removed work.
"""

import difflib
import math
from collections import Counter

import source_text

# A loop stops when the lines the passes removed, less the rewritten lines they wrote, are at least this share of the
# added lines, and the change added at least MIN_ADDED_LINES of them.
REMOVED_SHARE = 0.5
MIN_ADDED_LINES = 10
# A written line is a rewrite of a removed line when their text matches at least this closely (difflib ratio).
REWRITE_SIMILARITY = 0.8


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


def lost_lines_by_file(added_by_file, current_added_by_file, fix_added_by_file=None):
    """{path: Counter of the added lines the tree no longer adds} for each file that lost some of its added lines.
    `added_by_file` is {path: Counter} from added_lines; `current_added_by_file` is the same map for the source
    additions the tree holds over HEAD now, and a path it lacks added nothing. A line counts as kept when any file
    adds it now, so a move into another file is not a removal, and a line HEAD already holds is not kept by that copy.
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

    lost_by_file = {}
    for path, added in added_by_file.items():
        kept = added & current_lines
        current_lines -= kept
        lost = added - kept
        if lost:
            lost_by_file[path] = lost
    return lost_by_file


def lost_counts(lost_by_file):
    """{path: number of lines lost} for a map from `lost_lines_by_file`."""
    return {path: sum(lost.values()) for path, lost in lost_by_file.items()}


def rewritten_count(removed_lines, written_lines):
    """How many of the removed lines the fix passes wrote again with edits. Both arguments are Counters of line text.
    A written line counts only when it is a near copy of a removed line (REWRITE_SIMILARITY), and each line is
    matched once."""
    unmatched = {}
    for line in written_lines.elements():
        unmatched.setdefault(len(line), []).append(line)
    matched = 0
    for removed_line in removed_lines.elements():
        position = best_match_position(removed_line, unmatched)
        if position is None:
            continue
        length, index = position
        del unmatched[length][index]
        matched += 1
    return matched


def candidate_positions(lines_by_length, shortest, longest):
    """(length, index, line) for each line whose length is in shortest..longest."""
    for length in range(shortest, longest + 1):
        for index, line in enumerate(lines_by_length.get(length, ())):
            yield length, index, line


def best_match_position(removed_line, lines_by_length):
    """The (length, index) in `lines_by_length` ({length: [line]}) of the line most like `removed_line` at
    REWRITE_SIMILARITY or more, else None."""
    # A ratio of at least r needs 2 * shorter / (shorter + longer) >= r, which bounds the length of a candidate.
    size = len(removed_line)
    shortest = math.ceil(size * REWRITE_SIMILARITY / (2 - REWRITE_SIMILARITY) - 1e-9)
    longest = math.floor(size * (2 - REWRITE_SIMILARITY) / REWRITE_SIMILARITY + 1e-9)
    # One matcher per removed line: seq2 is indexed once, and each candidate is set as seq1.
    matcher = difflib.SequenceMatcher(None)
    matcher.set_seq2(removed_line)
    best_position = None
    best_ratio = REWRITE_SIMILARITY
    for length, index, candidate in candidate_positions(lines_by_length, shortest, longest):
        matcher.set_seq1(candidate)
        # The cheap upper bounds skip the full ratio for lines that cannot reach the best one so far.
        if matcher.real_quick_ratio() < best_ratio or matcher.quick_ratio() < best_ratio:
            continue
        ratio = matcher.ratio()
        if ratio >= best_ratio and (best_position is None or ratio > best_ratio):
            best_position = (length, index)
            best_ratio = ratio
    return best_position


def line_total(lines_by_file):
    """The number of lines in a {path: Counter} map."""
    total = 0
    for lines in lines_by_file.values():
        total += sum(lines.values())
    return total


def is_gutted(added_by_file, removed, written=0):
    """Whether `removed` ({path: lines}) less `written` (the removed lines the fix passes wrote again, see
    `rewritten_count`) is at least REMOVED_SHARE of the added lines, of a change that added at least MIN_ADDED_LINES.
    A pass that moves lines and edits them on the way writes about as many lines as it removes."""
    total = line_total(added_by_file)
    net_removed = sum(removed.values()) - written
    return total >= MIN_ADDED_LINES and net_removed >= total * REMOVED_SHARE


def removal_blocker(added_by_file, removed, written=0):
    """The blocker line for a gutted change: the counts, and the files that lost the most (up to three)."""
    total = line_total(added_by_file)
    lost = sum(removed.values())
    worst = sorted(removed, key=lambda path: (-removed[path], path))[:3]
    files = ", ".join(f"{path} ({removed[path]})" for path in worst)
    wrote = f" and wrote {written} of them again with edits" if written else ""
    return (f"the fix passes removed {lost} of the {total} source lines the change under review adds{wrote}; "
            f"most lost in {files}")
