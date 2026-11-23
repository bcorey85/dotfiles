"""protected_lines.py: put selected lines of a text back after a later edit changed them, and keep every other edit.

It knows nothing about what the lines mean: the caller names the 1-based line numbers of the earlier text to protect.
`changed_line_ranges` gives the changed stretches of both texts; `changed_stretches` filters it to the first text's."""
import difflib

# A changed line counts as the rewrite of a protected line when it is at least this much like it.
REWRITE_RATIO = 0.6


def entries_missing(before_entries, after_entries):
    """The (number, text) entries of `before_entries` whose text `after_entries` no longer holds, counting repeats."""
    remaining = {}
    for _number, text in after_entries:
        remaining[text] = remaining.get(text, 0) + 1
    missing = []
    for number, text in before_entries:
        if remaining.get(text, 0) > 0:
            remaining[text] -= 1
            continue
        missing.append((number, text))
    return missing


def changed_line_ranges(before_text, after_text):
    """The (tag, before_start, before_end, after_start, after_end) of each stretch that differs between the two texts:
    0-based line indexes, exclusive ends, tag one of `insert`, `delete` or `replace`. [] for equal texts."""
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    return [opcode for opcode in matcher.get_opcodes() if opcode[0] != "equal"]


def changed_stretches(before_text, after_text):
    """The (first, last) 1-based line numbers of `before_text` of each stretch that `after_text` removed or rewrote."""
    ranges = changed_line_ranges(before_text, after_text)
    return [
        (start + 1, end)
        for tag, start, end, _after_start, _after_end in ranges
        if tag in ("delete", "replace")
    ]


def consecutive_runs(entries):
    """The (first, last) line numbers of each run of consecutive lines in the (number, text) `entries`."""
    runs = []
    for number, _text in entries:
        if runs and runs[-1][1] == number - 1:
            runs[-1] = (runs[-1][0], number)
            continue
        runs.append((number, number))
    return runs


def in_span_with(number, spans, named_lines):
    """True when `number` lies in a (first, last) span that also holds one of `named_lines`."""
    return any(
        first <= number <= last and any(first <= line <= last for line in named_lines)
        for first, last in spans
    )


def restore_protected_lines(before_text, after_text, protected_numbers, whole_stretch=True, may_replace=None):
    """`after_text` with each protected line of `before_text` that it changed or removed put back. `protected_numbers`
    are 1-based line numbers of `before_text`. A stretch that was removed is restored whole, or only at its protected
    lines when `whole_stretch` is False. In a stretch that was rewritten, each protected line replaces its closest
    rewrite, and the other lines of the stretch stay, so a line someone else added beside the rewrite is kept. When
    `may_replace` is given, only a stretch line it accepts (called with the line's text) can be replaced."""
    protected = {number - 1 for number in protected_numbers}
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    restored = []
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        lost_in_stretch = sorted(protected.intersection(range(before_start, before_end)))
        if tag == "delete" and lost_in_stretch and whole_stretch:
            restored += before_lines[before_start:before_end]
        elif tag == "delete" and lost_in_stretch:
            restored += [before_lines[index] for index in lost_in_stretch]
        elif tag == "replace" and lost_in_stretch:
            restored += rewritten_stretch(before_lines, lost_in_stretch, after_lines[after_start:after_end],
                                          may_replace)
        else:
            restored += after_lines[after_start:after_end]
    return "".join(restored)


def rewritten_stretch(before_lines, lost_indexes, stretch_lines, may_replace=None):
    """The lines of one rewritten stretch with each lost line of `before_lines` back: in place of the stretch line most
    like it that `may_replace` accepts, or in front of the stretch when no line is alike."""
    lines = list(stretch_lines)
    taken = set()
    unmatched = []
    for index in lost_indexes:
        original = before_lines[index]
        match = closest_line(original, lines, taken, may_replace)
        if match is None:
            unmatched.append(original)
            continue
        lines[match] = original
        taken.add(match)
    return unmatched + lines


def closest_line(original, lines, taken, may_replace=None):
    """The index in `lines`, outside `taken`, of the line most like `original` at REWRITE_RATIO or better, among the
    lines `may_replace` accepts (all when it is None); None when no line is."""
    best_index, best_ratio = None, REWRITE_RATIO
    for index, line in enumerate(lines):
        if index in taken:
            continue
        if may_replace is not None and not may_replace(line):
            continue
        ratio = difflib.SequenceMatcher(None, original, line).ratio()
        if ratio >= best_ratio:
            best_index, best_ratio = index, ratio
    return best_index
