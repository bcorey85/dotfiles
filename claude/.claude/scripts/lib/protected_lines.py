"""protected_lines.py: put selected lines of a text back after a later edit changed them, and keep every other edit.

It knows nothing about what the lines mean: the caller names the 1-based line numbers of the earlier text to protect.
`changed_line_ranges` gives the changed stretches of both texts; `changed_stretches` filters it to the first text's.
`lines_rewritten_in_place` says whether replaced lines are rewrites of their old lines."""
import difflib
import typing

import script_utils

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


def with_final_newline(text):
    """`text` ending in a newline. A missing final newline makes the last line differ from the same line with one, which
    hides a swap of the last two lines from a diff."""
    return text if text.endswith("\n") else text + "\n"


def lines_rewritten_in_place(before_lines, after_lines, rival_lines):
    """True when each of `before_lines`, in order, is like its own line of `after_lines` at REWRITE_RATIO or better,
    and no line of `rival_lines` is more like it than its own (an update in place, not a reorder).
    Each old line takes the most like such new line (the earliest on a tie) after the previous match, so no two
    share one."""
    # Not `closest_line`: that one breaks ties on the latest line and returns no score, and this order check needs the
    # earliest line and its score.
    next_index = 0
    for before_line in before_lines:
        own_index = None
        own_score = 0.0
        for index in range(next_index, len(after_lines)):
            score = script_utils.text_similarity(before_line, after_lines[index])
            if score >= REWRITE_RATIO and score > own_score:
                own_index = index
                own_score = score
        if own_index is None:
            return False
        for rival_line in rival_lines:
            if script_utils.text_similarity(before_line, rival_line) > own_score:
                return False
        next_index = own_index + 1
    return True


def entries_missing_in_stretches(before_entries, after_entries, stretches):
    """The `entries_missing` entries, with each repeated text counted at the copy the alignment lost: of the entries
    that share a missing text, the ones lying in a (first, last) of `stretches` come first, so a copy that sits in an
    unchanged stretch is not named in place of the copy the edit removed. Keeps the order of `before_entries`."""
    missing = entries_missing(before_entries, after_entries)
    missing_counts = {}
    for _number, text in missing:
        missing_counts[text] = missing_counts.get(text, 0) + 1
    chosen = []
    for number, text in before_entries:
        if missing_counts.get(text, 0) == 0:
            continue
        if not any(first <= number <= last for first, last in stretches):
            continue
        missing_counts[text] -= 1
        chosen.append((number, text))
    return chosen


def line_opcodes(before_text, after_text):
    """`(before_lines, after_lines, opcodes)`: both texts split into lines and the difflib opcodes that align them.
    `changed_stretches`, `rewritten_stretches` and `restore_protected_lines` read their alignment from this one, so
    their line numbers agree."""
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    return before_lines, after_lines, matcher.get_opcodes()


def changed_line_ranges(before_text, after_text):
    """The (tag, before_start, before_end, after_start, after_end) of each stretch that differs between the two texts:
    0-based line indexes, exclusive ends, tag one of `insert`, `delete` or `replace`. [] for equal texts."""
    _before_lines, _after_lines, opcodes = line_opcodes(before_text, after_text)
    return [opcode for opcode in opcodes if opcode[0] != "equal"]


def changed_stretches(before_text, after_text):
    """The (first, last) 1-based line numbers of `before_text` of each stretch that `after_text` removed or rewrote."""
    _before_lines, _after_lines, opcodes = line_opcodes(before_text, after_text)
    stretches = []
    for tag, before_start, before_end, _after_start, _after_end in opcodes:
        if tag in ("delete", "replace"):
            stretches.append((before_start + 1, before_end))
    return stretches


class Rewrite(typing.NamedTuple):
    """One stretch `after_text` rewrote: the (first, last) 1-based line numbers it held in the text before, and the
    (first, last) it holds in the text after."""

    before: tuple
    after: tuple


def rewritten_stretches(before_text, after_text):
    """The Rewrite of each stretch of `before_text` that `after_text` replaced with other lines (a pure removal is no
    rewrite)."""
    _before_lines, _after_lines, opcodes = line_opcodes(before_text, after_text)
    rewrites = []
    for tag, before_start, before_end, after_start, after_end in opcodes:
        if tag == "replace":
            rewrites.append(Rewrite((before_start + 1, before_end), (after_start + 1, after_end)))
    return rewrites


def consecutive_runs(entries):
    """The (first, last) line numbers of each run of consecutive lines in the (number, text) `entries`."""
    runs = []
    for number, _text in entries:
        if runs and runs[-1][1] == number - 1:
            runs[-1] = (runs[-1][0], number)
            continue
        runs.append((number, number))
    return runs


def consecutive_entry_runs(entries):
    """The (number, text) `entries` split into blocks, one for each run of consecutive line numbers."""
    return [[entry for entry in entries if first <= entry[0] <= last]
            for first, last in consecutive_runs(entries)]


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
    before_lines, after_lines, opcodes = line_opcodes(before_text, after_text)
    restored = []
    for tag, before_start, before_end, after_start, after_end in opcodes:
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
    like it that `may_replace` accepts, or, when no line is alike, right after the last lost line placed before it (in
    front of the stretch when none was)."""
    lines = list(stretch_lines)
    taken = set()
    in_front = []
    after_slot = [[] for _line in lines]
    last_placed = None
    for index in lost_indexes:
        original = before_lines[index]
        match = closest_line(original, lines, taken, may_replace)
        if match is not None:
            lines[match] = original
            taken.add(match)
            last_placed = match
        elif last_placed is None:
            in_front.append(original)
        else:
            after_slot[last_placed].append(original)
    restored = list(in_front)
    for line, extras in zip(lines, after_slot, strict=True):
        restored.append(line)
        restored += extras
    return restored


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
