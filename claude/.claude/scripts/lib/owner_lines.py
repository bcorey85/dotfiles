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
    """True when each of `before_lines`, in order, is like its own line of `after_lines` at REWRITE_RATIO or better.
    Each old line takes the first such new line after the previous match, so no two share one."""
    next_index = 0
    for before_line in before_lines:
        for index in range(next_index, len(after_lines)):
            if script_utils.text_similarity(before_line, after_lines[index]) >= protected_lines.REWRITE_RATIO:
                next_index = index + 1
                break
        else:
            return False
    return True


def owner_lines_only(before_text, after_text):
    """True when `after_text` differs from `before_text` only by owner bullets added or updated in the Owners section.
    An updated bullet must still resemble its old text; an unrelated bullet put in place of one is a removal.
    A delete, merge, drop, prose line, other section or renamed heading is False. A reorder is False, except two or
    more bullets that resemble each other, reworded and moved, which pass as updates in place."""
    # A missing final newline would make the last line differ from the same line with one, hiding a swap from the diff.
    before_text = before_text if before_text.endswith("\n") else before_text + "\n"
    after_text = after_text if after_text.endswith("\n") else after_text + "\n"
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
        before_block = before_lines[before_start:before_end]
        after_block = after_lines[after_start:after_end]
        if not every_line_resembled(before_block, after_block):
            return False
    return True
