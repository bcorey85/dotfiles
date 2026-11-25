"""signoff_lines.py: the one reader for the sign-off lines of a decision log: the lines where a ruling is recorded,
with the entry each one belongs to."""
import re

import plan_format
import script_utils

# The `... by` forms of a decision-log line that records who ruled: `Ruled by <who>`, `Rulings by <who>`,
# `Adopted by`, `decided by`, `cut|reworded|narrowed by`. The ruling text of an entry opens with `The ruling:`
# (the form `ruling_deviation` writes).
RULED_BY_FORMS = r"rul(?:ed|ings?)|adopted|decided|cut|reworded|narrowed"
RULED_BY = re.compile(rf"\b(?:{RULED_BY_FORMS})\s+by\b", re.I)
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


def signoff_entry_ranges(text, name=""):
    """The sign-off entries of a decision log as [(start, end)] 0-based half-open line ranges: each entry with a line
    that holds a ruling marker, from the line that opens it through its wrapped and nested lines. The marker line is
    in the lines `signoff_scope_indexes` gives for the file `name`; the range itself may start outside them (an
    indented entry under the `## Plan Deviations` heading), so a reader keeps only the in-scope lines."""
    lines = text.splitlines()
    scope_indexes = signoff_scope_indexes(name, lines)
    ranges = {}
    for index in sorted(scope_indexes):
        if not is_signoff_marker(lines[index]):
            continue
        start = entry_start(lines, index)
        ranges[start] = continuation_end(lines, start)
    return sorted(ranges.items())


def signoff_lines(text, name=""):
    """The sign-off lines of a decision log as [(1-based line number, line text)]: each entry with a line that holds a
    ruling marker (`Ruled by`, `Rulings by`, `Adopted by`, `sign-off`, `ruling`, a `The ruling:` line), from the line
    that opens the entry through its wrapped and nested lines. Only the lines `signoff_scope_indexes` gives for the
    file `name` are read; an empty `name` reads a text with no `## Plan Deviations` section whole."""
    lines = text.splitlines()
    scope_indexes = signoff_scope_indexes(name, lines)
    found = set()
    for start, end in signoff_entry_ranges(text, name):
        found.update(range(start, end))
    return [(index + 1, lines[index]) for index in sorted(found & scope_indexes)]


# The owner after a `RULED_BY_FORMS` word and `by`, or after `Signed off by`: up to the next `.`, `,`, `:` or `;`. The
# owner of a user ruling opens with a user name (see `is_user_ruled_line`); any other owner is a session.
RULED_BY_OWNER = re.compile(rf"\b(?:{RULED_BY_FORMS}|{SIGNED_OFF.pattern})\s+by\s+([^.,:;]+)", re.I)
RULING_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
USER_RULING_LABEL = re.compile(r"user ruling\b", re.I)
USER_VERBS = r"(?:ruled|approved|signed off)\b"
# A heading that closes with its owner and date: `## Signed off: <what> (user, 2026-11-21)`.
TRAILING_OWNER = re.compile(rf"\(([^(),]+),\s*{RULING_DATE.pattern}\)\s*$")
BARE_USER_OWNER = "user"
MIN_QUOTE_WORDS = 3
# A line that leads into the user's own name: `User sign-off, <name>, <date>` or `user sign-off: <name>`.
USER_SIGNOFF_OWNER = re.compile(r"\buser\s+sign-off[,:]\s+([^.,:;]+)", re.I)
# A subject at the start of a sentence: at the line start, or after `.`, `:` or `;` and a space.
SENTENCE_START = r"(?:^|[.:;]\s+)"


def is_user_ruled_line(line, user_names):
    """True when the line records a dated ruling by the user: its owner after `<form> by` opens with one of
    `user_names` (what `plan_format.ruling_owner` writes for `--by user`: the git user name or `the user`), it opens
    with a `User ruling` label, its subject, at the start of a sentence, is one of `user_names` followed by `ruled`,
    `approved` or `signed off`, it closes with a `(<user name or user>, <date>)` owner, or it holds
    `User sign-off, <user name>`. Any other owner, such as a session name, is a session."""
    if not RULING_DATE.search(line):
        return False
    words = plan_format.normalized_words(BULLET_LINE.sub("", line)).lower()
    if USER_RULING_LABEL.match(words):
        return True
    names = [re.escape(name.lower()) for name in user_names]
    if any(re.search(rf"{SENTENCE_START}{name}\s+{USER_VERBS}", words) for name in names):
        return True
    trailing = TRAILING_OWNER.search(line)
    if trailing is not None and is_user_owner(trailing.group(1), user_names):
        return True
    signoff = USER_SIGNOFF_OWNER.search(line)
    if signoff is not None and is_user_owner(signoff.group(1), user_names):
        return True
    owner = RULED_BY_OWNER.search(line)
    if owner is None:
        return False
    return is_user_owner(owner.group(1), user_names)


def is_user_owner(owner_text, user_names):
    """True when the owner text opens with one of `user_names` or is the bare word `user`."""
    owner_words = plan_format.normalized_words(owner_text).lower()
    if owner_words == BARE_USER_OWNER:
        return True
    # `the user's standing rule` is a session ruling: an apostrophe after the name is no word end.
    return any(re.match(rf"{re.escape(name.lower())}\b(?!['\N{{RIGHT SINGLE QUOTATION MARK}}])", owner_words)
               for name in user_names)


def cites_user_ruling(impact_text, log_text, log_names, user_names, name=""):
    """True when `impact_text` names the log (any of `log_names`, case-insensitive) and either quotes, whitespace
    normalized, or points at the number of (`<log name>:<n>` or `<log name> line <n>`) a line of a user-ruled
    sign-off entry of `log_text`. Only lines inside `signoff_scope_indexes` count. A quote needs three or more words
    (`MIN_QUOTE_WORDS`) unless the entry is one line, and the `The ruling:` text counts with or without its label.
    A `The ruling:` entry is judged together with the dated entry above it (`ruling_units`). `name` is the log's
    file name, as for `signoff_lines`."""
    impact = plan_format.normalized_words(impact_text).lower()
    named = [log_name for log_name in log_names if log_name.lower() in impact]
    if not named:
        return False
    lines = log_text.splitlines()
    scope_indexes = signoff_scope_indexes(name, lines)
    for unit in ruling_units(lines, signoff_entry_ranges(log_text, name)):
        indexes = [index for start, end in unit for index in range(start, end) if index in scope_indexes]
        if not any(is_user_ruled_line(lines[index], user_names) for index in indexes):
            continue
        for index in indexes:
            plain_line = BULLET_LINE.sub("", lines[index])
            # The ruling text counts with and without its `The ruling:` label.
            for quote_line in (plain_line, RULING_TEXT_LINE.sub("", plain_line)):
                quoted = plan_format.normalized_words(quote_line).lower()
                # A short line (a nested `- AC3`) is no quote unless it is the whole entry.
                if len(quoted.split()) < MIN_QUOTE_WORDS and len(indexes) > 1:
                    continue
                if quoted and quoted in impact:
                    return True
        if names_a_line_of(impact, named, [index + 1 for index in indexes]):
            return True
    return False


def ruling_units(lines, ranges):
    """The entry `ranges` grouped into units: an entry that opens with `The ruling:` (what `ruling_deviation` writes
    after a blank line) joins the closest entry above it."""
    units = []
    for start, end in ranges:
        if units and RULING_TEXT_LINE.match(lines[start]):
            units[-1].append((start, end))
            continue
        units.append([(start, end)])
    return units


def names_a_line_of(impact, log_names, numbers):
    """True when `impact` points at one of the 1-based line `numbers` as `<log name>:<n>` or `<log name> line <n>`."""
    for log_name in log_names:
        for number in numbers:
            pointer = rf"{re.escape(log_name.lower())}(?::|\s+line\s+){number}\b"
            if re.search(pointer, impact):
                return True
    return False
