"""ruled_change_text.py: the words a finding carries when the user, a session or an unnamed ruler changed an ask's
proposed change, and the reading of a "no code change" ruling out of them. Imports only the standard library."""
import re

USER_CLAUSE = "The user changed it"
SESSION_CLAUSE = "The session changed it, not the user"
UNNAMED_CLAUSE = "It was changed at the ruling"
PLACE_MARKER = "; make this change in its place: "
NO_CODE_RULING = re.compile(r"\bno code change", re.IGNORECASE)


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


def is_no_code_ruling(note):
    """Whether a ruling note says the change is no code change."""
    return NO_CODE_RULING.search(note) is not None


def is_no_code_finding(finding_text):
    """Whether a finding's text carries a ruling note that says no code change."""
    note = ruled_note(finding_text)
    if note is None:
        return False
    return is_no_code_ruling(note)
