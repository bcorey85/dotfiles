"""signoff_lines.py: the one reader for the sign-off lines of a decision log: the lines where a ruling is recorded,
with the entry each one belongs to."""
import re

import plan_format
import script_utils

# The `... by` forms of a decision-log line that records who ruled: `Ruled by <who>`, `Rulings by <who>`,
# `Adopted by`, `decided by`, `cut|reworded|narrowed by`. The ruling text of an entry opens with `The ruling:`
# (the form `ruling_deviation` writes).
RULED_BY = re.compile(r"\b(?:rul(?:ed|ings?)|adopted|decided|cut|reworded|narrowed)\s+by\b", re.I)
SIGNED_OFF = re.compile(r"\bsigned\s+off\b", re.I)
RULING_TEXT_LINE = re.compile(r"^\s*" + re.escape(plan_format.DEVIATION_RULING_PREFIX.strip()), re.I)
BULLET_LINE = re.compile(r"^(\s*)[-*]\s")
DISAGREEMENT_LINE = re.compile(r"^\s*the disagreement:", re.I)
# A plural ruling heading, such as `### Damage-path rulings (user, ...)`, which `SESSION_RULING_MARK` does not match.
RULINGS_WORD = re.compile(r"\brulings\b", re.I)


def is_signoff_marker(line):
    """True when the line holds a `... by` ruling form (`RULED_BY`), `signed off`, a sign-off or ruling word
    (`SESSION_RULING_MARK`: `sign-off`, `ruled`, `ruling`), the word `rulings`, or opens with `The ruling:`."""
    ruling_word = plan_format.SESSION_RULING_MARK.search(line) or RULINGS_WORD.search(line)
    return bool(records_ruler(line) or ruling_word or RULING_TEXT_LINE.match(line))


def entry_start(lines, index):
    """The index of the line that opens the entry the line at `index` belongs to: the line itself, or, for a wrapped
    line, the nearest line above it that is a bullet or is not indented."""
    while index > 0 and lines[index][:1].isspace() and not BULLET_LINE.match(lines[index]):
        if not lines[index - 1].strip():
            break
        index -= 1
    return index


def continuation_end(lines, start):
    """The index after the lines that follow the entry line at `start`: indented, not blank, not the start of a
    bullet at the entry's own indent or above, and not the disagreement block. Nested sub-bullets belong to the
    entry."""
    entry_indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if not line.strip() or not line[0].isspace() or DISAGREEMENT_LINE.match(line):
            break
        bullet = BULLET_LINE.match(line)
        if bullet and len(bullet.group(1)) <= entry_indent:
            break
        end += 1
    return end


def signoff_scope_indexes(name, lines):
    """The 0-based indexes of the lines of the file `name` where a ruling is recorded: every line of `03-decisions.md`;
    the `## Plan Deviations` section of a file that has one; none of a `plan.md`, `spec.md`, criteria file or ticket
    with no such section; every line of any other file (an evidence file)."""
    if name == plan_format.DECISION_LOG_NAME:
        return set(range(len(lines)))
    section = script_utils.heading_section_indexes(lines, plan_format.DEVIATIONS_HEADING)
    if section:
        return set(section)
    prose_names = (plan_format.PLAN_ONLY_PLAN_NAME, plan_format.CRITERIA_FILE_NAME, plan_format.SPEC_FILE_NAME,
                   plan_format.QUESTIONS_FILE_NAME, plan_format.RESEARCH_FILE_NAME)
    prose_file = name in prose_names or name.endswith(plan_format.TICKET_FILE_NAME)
    return set() if prose_file else set(range(len(lines)))


def signoff_lines(text, name=""):
    """The sign-off lines of a decision log as [(1-based line number, line text)]: each entry with a line that
    `is_signoff_marker` matches, from the line that opens the entry through its wrapped and nested lines. Only the
    lines `signoff_scope_indexes` gives for the file `name` are read; an empty `name` reads a text with no
    `## Plan Deviations` section whole."""
    lines = text.splitlines()
    scope_indexes = signoff_scope_indexes(name, lines)
    found = set()
    for index in sorted(scope_indexes):
        if index in found or not is_signoff_marker(lines[index]):
            continue
        start = entry_start(lines, index)
        found.update(range(start, continuation_end(lines, start)))
    return [(index + 1, lines[index]) for index in sorted(found & scope_indexes)]


# A session is the ruler of a line only through its `by` clause: `Ruled by the session, not the user`, or `by` a
# (the, this) orchestrating or lane session, or a ruler named `(orchestrating session)`.
SESSION_RULER = re.compile(re.escape(plan_format.SESSION_RULING_OWNER)
                           + r"|\bby\s+(?:(?:the|this|a)\s+)?(?:orchestrating|lane)[\s-]+session\b"
                           + r"|\((?:the\s+)?(?:orchestrating|lane)\s+session\)", re.I)
# A clause that records the user's sign-off: `user sign-off`, `sign-off: <name>`, `user-signed`, or `signed off by`
# anyone but a session. It wins over a session ruler on the same line.
USER_SIGNOFF = re.compile(r"\buser[\s-]+sign-?\s*off\b|\bsign-?\s*off\s*:\s*\S|\buser[\s-]+signed\b"
                          r"|\bsigned\s+off\s+by\s+(?!(?:the\s+|this\s+)?(?:(?:orchestrating|lane)[\s-]+)?session\b)",
                          re.I)


def is_session_ruled(line):
    """True when a session is the line's ruler and no clause of the line records the user's sign-off. It fails
    closed: a line with neither reads as the user's."""
    if USER_SIGNOFF.search(line):
        return False
    return bool(SESSION_RULER.search(line))


def records_ruler(line):
    """True when the line holds a `... by` ruling form or `signed off`."""
    return bool(RULED_BY.search(line) or SIGNED_OFF.search(line))


def is_ruler_marker(line):
    """True when the line is a sign-off marker other than a `The ruling:` line, which holds the ruled text. A marker
    that names no ruler reads as the user's in `records_user_signoff`."""
    return is_signoff_marker(line) and not RULING_TEXT_LINE.match(line)


def disagreement_indexes(lines):
    """The indexes of the lines of each `The disagreement:` block, which quotes a reviewer's objection and records no
    ruler: from the `The disagreement:` line through its last continuation line."""
    found = set()
    for index, line in enumerate(lines):
        if DISAGREEMENT_LINE.match(line):
            found.update(range(index, continuation_end(lines, index)))
    return found


def ruler_marker_indexes(lines, index, scope):
    """The indexes of the marker lines in `scope` whose ruler the line at `index` has: the marker lines inside its
    entry. An entry that opens with `The ruling:` or `The disagreement:` (the block `ruling_deviation` writes, set
    apart by a blank line) takes the nearest marker above it, else the nearest one below. Any other entry with no
    marker line gets none. Lines of a disagreement block are never markers."""
    scope = scope - disagreement_indexes(lines)

    def is_scoped_marker(number):
        return number in scope and is_ruler_marker(lines[number])

    start = entry_start(lines, index)
    in_entry = [number for number in range(start, continuation_end(lines, start)) if is_scoped_marker(number)]
    if in_entry:
        return in_entry
    opens_block = RULING_TEXT_LINE.match(lines[start]) or DISAGREEMENT_LINE.match(lines[start])
    if not opens_block:
        return []
    above = [number for number in range(index, -1, -1) if is_scoped_marker(number)]
    if above:
        return above[:1]
    below = [number for number in range(index + 1, len(lines)) if is_scoped_marker(number)]
    return below[:1]


def file_has_user_marker(lines, scope):
    """True when a marker line in `scope`, outside a disagreement block, does not name the session."""
    scope = scope - disagreement_indexes(lines)
    return any(is_ruler_marker(lines[number]) and not is_session_ruled(lines[number]) for number in sorted(scope))


def records_user_signoff(text, line_number, name=""):
    """True when the sign-off line `line_number` (1-based) of the file `name` with text `text` belongs to an entry
    whose ruler is not the session. Only the lines `signoff_scope_indexes` gives for `name` are read. It fails closed:
    any marker line the entry holds that does not name the session reads as the user's, so a session ruling never
    stands in for it. A line whose entry has no marker line reads as the user's when the file has one. A text with no
    marker line reads as no user sign-off. Line 0 names the file, so it records a user sign-off when any marker line
    of the file does not name the session."""
    lines = text.splitlines()
    scope = signoff_scope_indexes(name, lines)
    if line_number == 0:
        return file_has_user_marker(lines, scope)
    markers = ruler_marker_indexes(lines, line_number - 1, scope)
    if markers:
        return any(not is_session_ruled(lines[number]) for number in markers)
    return file_has_user_marker(lines, scope)
