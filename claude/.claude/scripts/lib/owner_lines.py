"""owner_lines.py: the one reader of the owner-line format of the scripts CLAUDE.md (`SCRIPTS_CLAUDE_MD`), and the
test for an edit that only adds or updates owner lines. This module owns the fact."""
import re

import protected_lines
import script_utils

SCRIPTS_CLAUDE_MD = "claude/.claude/scripts/CLAUDE.md"
OWNERS_HEADING = "Owners"
# A bullet that names a fact, a colon, and a backticked module path.
OWNER_LINE = re.compile(r"^- [^:]+: .*`[\w./-]+\.(?:py|ts|sh)`")


def owner_line_indexes(lines):
    """The 0-based indexes of the owner bullets inside the Owners section of `lines`."""
    section = script_utils.heading_section_indexes(lines, OWNERS_HEADING)
    return {index for index in section if OWNER_LINE.match(lines[index])}


def every_line_resembled(before_lines, after_lines):
    """True when each of `before_lines` is like its own line of `after_lines` at REWRITE_RATIO or better: no two
    old lines share a new line, and the matched new lines keep the order of the old ones."""
    taken = set()
    previous_index = -1
    for before_line in before_lines:
        match = protected_lines.closest_line(before_line, after_lines, taken)
        if match is None or match <= previous_index:
            return False
        taken.add(match)
        previous_index = match
    return True


def owner_lines_only(before_text, after_text):
    """True when `after_text` differs from `before_text` only by owner bullets added or updated in the Owners section.
    An updated bullet must still resemble its old text; an unrelated bullet put in place of one is a removal.
    A delete, merge, drop, reorder, prose line, other section or renamed heading is False."""
    ranges = protected_lines.changed_line_ranges(before_text, after_text)
    if not ranges:
        return False
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    before_owner = owner_line_indexes(before_lines)
    after_owner = owner_line_indexes(after_lines)
    for tag, before_start, before_end, after_start, after_end in ranges:
        if before_end - before_start > after_end - after_start:
            return False
        if not set(range(before_start, before_end)) <= before_owner:
            return False
        if not set(range(after_start, after_end)) <= after_owner:
            return False
        if tag != "replace":
            continue
        if not every_line_resembled(before_lines[before_start:before_end], after_lines[after_start:after_end]):
            return False
    return True
