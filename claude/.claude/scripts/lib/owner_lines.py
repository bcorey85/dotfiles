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


def owner_lines_only(before_text, after_text):
    """True when `after_text` differs from `before_text` only by owner bullets added or updated in the Owners section.
    An updated bullet must still resemble its old text; an unrelated bullet put in place of one is a removal.
    A delete, merge, drop, prose line, other section or renamed heading is False. A reorder is False, even of
    bullets that resemble each other and are reworded, even with an unchanged bullet between them."""
    before_text = protected_lines.with_final_newline(before_text)
    after_text = protected_lines.with_final_newline(after_text)
    ranges = protected_lines.changed_line_ranges(before_text, after_text)
    if not ranges:
        return False
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    before_owner = owner_line_indexes(before_lines)
    after_owner = owner_line_indexes(after_lines)
    changed_after = {index for _, _, _, start, end in ranges for index in range(start, end)}
    # An unchanged bullet sits in an equal stretch and already matches its own old line, so it cannot be where a
    # moved line went.
    after_owner_lines = [after_lines[index] for index in sorted(changed_after & after_owner)]
    for tag, before_start, before_end, after_start, after_end in ranges:
        if before_end - before_start > after_end - after_start:
            return False
        if not set(range(before_start, before_end)) <= before_owner:
            return False
        if not set(range(after_start, after_end)) <= after_owner:
            return False
        if tag != "replace":
            continue
        before_block = before_lines[before_start:before_end]
        after_block = after_lines[after_start:after_end]
        if not protected_lines.lines_rewritten_in_place(before_block, after_block, after_owner_lines):
            return False
    return True
