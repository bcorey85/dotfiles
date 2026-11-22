"""ruled_change_text.py: the words a finding carries when the user, a session or an unnamed ruler changed an ask's
proposed change, and the reading of a "no code change" ruling out of them. Imports only the standard library."""
import re

USER_CLAUSE = "The user changed it"
SESSION_CLAUSE = "The session changed it, not the user"
UNNAMED_CLAUSE = "It was changed at the ruling"
PLACE_MARKER = "; make this change in its place: "
NO_CODE_RULING = re.compile(r"\bno code change", re.IGNORECASE)
CLAUSE_BREAK = re.compile(r"[;,]|:(?=\s|$)|\((?!\))|(?<!\()\)|\.(?=\s|$)|\s*(?:--|[\N{EN DASH}\N{EM DASH}])\s*|\s-\s")
_EDIT_VERB_START_TEXT = (
    r"\s*(?:(?:but|and|also|then|plus|please|just|instead|so|now|still)\s+)*"
    r"(?:add|pin|change|extend|cover|update|write|create|include|adjust|fix)\b"
)
EDIT_VERB_START = re.compile(_EDIT_VERB_START_TEXT, re.IGNORECASE)
NEGATED_EDIT = re.compile(_EDIT_VERB_START_TEXT + r"\s+(?:no|nothing|none|not)\b", re.IGNORECASE)
# Underscore counts as a word break, so the test word in a name like test_x.py is found.
TEST_WORD = re.compile(r"(?<![^\W_])(?:tests?|cases?|fixtures?)(?![^\W_])", re.IGNORECASE)


def changed_text(base, note, ruler_clause):
    """`base` followed by the ruling's `note`, behind the ruler's clause and the marker `ruled_note` finds."""
    return f"{base} {ruler_clause}{PLACE_MARKER}{note}"


def ruled_note(finding_text):
    """The note after the last marker in a finding's text, or None when the text carries none. Every ruler's clause
    ends in the same marker, and the latest ruling wins."""
    _before, marker, note = finding_text.rpartition(PLACE_MARKER)
    if not marker:
        return None
    return note


def asks_for_test_edit(clause):
    """Whether a clause starts with an edit verb (optionally after a lead-in such as but, and, also, then or
    plus), not followed by no/nothing/none/not, and names a test."""
    if EDIT_VERB_START.match(clause) is None:
        return False
    if NEGATED_EDIT.match(clause) is not None:
        return False
    return TEST_WORD.search(clause) is not None


def is_no_code_ruling(note):
    """Whether a ruling note says the change is no code change and asks for no test edit after those words. A
    clause that starts with an edit verb (optionally after a lead-in such as but, and, also, then or plus) and
    names a test is an edit, unless the verb is negated (add no, change nothing): the fixer must make it."""
    found = NO_CODE_RULING.search(note)
    if found is None:
        return False
    after_the_words = note[found.end():]
    clauses = CLAUSE_BREAK.split(after_the_words)
    return not any(asks_for_test_edit(clause) for clause in clauses)


def is_no_code_finding(finding_text):
    """Whether a finding's text carries a ruling note that says no code change."""
    note = ruled_note(finding_text)
    if note is None:
        return False
    return is_no_code_ruling(note)
