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


def is_signoff_marker(line):
    """True when the line holds a `... by` ruling form (`RULED_BY`), `signed off`, a sign-off or ruling word
    (`SESSION_RULING_MARK`: `sign-off`, `ruled`, `ruling`), or opens with `The ruling:`."""
    return bool(RULED_BY.search(line) or SIGNED_OFF.search(line) or plan_format.SESSION_RULING_MARK.search(line)
                or RULING_TEXT_LINE.match(line))


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
    """The sign-off lines of a decision log as [(1-based line number, line text)]: each entry with a line that holds a
    ruling marker (`Ruled by`, `Rulings by`, `Adopted by`, `sign-off`, `ruling`, a `The ruling:` line), from the line
    that opens the entry through its wrapped and nested lines. Only the lines `signoff_scope_indexes` gives for the
    file `name` are read; an empty `name` reads a text with no `## Plan Deviations` section whole."""
    lines = text.splitlines()
    scope_indexes = signoff_scope_indexes(name, lines)
    found = set()
    for index in sorted(scope_indexes):
        if index in found or not is_signoff_marker(lines[index]):
            continue
        start = entry_start(lines, index)
        found.update(range(start, continuation_end(lines, start)))
    return [(index + 1, lines[index]) for index in sorted(found & scope_indexes)]
