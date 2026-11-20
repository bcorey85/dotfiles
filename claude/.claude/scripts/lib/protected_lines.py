"""protected_lines.py: put selected lines of a text back after a later edit changed them, and keep every other edit.

It knows nothing about what the lines mean: the caller names the 1-based line numbers of the earlier text to protect."""
import difflib

# A changed line counts as the rewrite of a protected line when it is at least this much like it.
REWRITE_RATIO = 0.6


def restore_protected_lines(before_text, after_text, protected_numbers):
    """`after_text` with each protected line of `before_text` that it changed or removed put back. `protected_numbers`
    are 1-based line numbers of `before_text`. A stretch that was removed is restored whole. In a stretch that was
    rewritten, each protected line replaces its closest rewrite, and the other lines of the stretch stay, so a line
    someone else added beside the rewrite is kept."""
    protected = {number - 1 for number in protected_numbers}
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    restored = []
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        lost_in_stretch = sorted(protected.intersection(range(before_start, before_end)))
        if tag == "delete" and lost_in_stretch:
            restored += before_lines[before_start:before_end]
        elif tag == "replace" and lost_in_stretch:
            restored += rewritten_stretch(before_lines, lost_in_stretch, after_lines[after_start:after_end])
        else:
            restored += after_lines[after_start:after_end]
    return "".join(restored)


def rewritten_stretch(before_lines, lost_indexes, stretch_lines):
    """The lines of one rewritten stretch with each lost line of `before_lines` back: in place of the stretch line most
    like it, or in front of the stretch when no line is alike."""
    lines = list(stretch_lines)
    taken = set()
    unmatched = []
    for index in lost_indexes:
        original = before_lines[index]
        match = closest_line(original, lines, taken)
        if match is None:
            unmatched.append(original)
            continue
        lines[match] = original
        taken.add(match)
    return unmatched + lines


def closest_line(original, lines, taken):
    """The index in `lines`, outside `taken`, of the line most like `original` at REWRITE_RATIO or better; None when no
    line is."""
    best_index, best_ratio = None, REWRITE_RATIO
    for index, line in enumerate(lines):
        if index in taken:
            continue
        ratio = difflib.SequenceMatcher(None, original, line).ratio()
        if ratio >= best_ratio:
            best_index, best_ratio = index, ratio
    return best_index
