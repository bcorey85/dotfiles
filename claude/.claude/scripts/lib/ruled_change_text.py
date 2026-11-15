"""ruled_change_text.py: the words a finding carries when the user or a session changed an ask's proposed change, and
the reading of a "no code change" ruling out of them. Imports only the standard library."""
import re

CHANGED_MARKER = " The user changed it; make this change in its place: "
NO_CODE_RULING = re.compile(r"\bno code change", re.IGNORECASE)


def changed_text(base, note):
    """`base` followed by the ruling's `note`, behind the marker `ruled_note` finds."""
    return f"{base}{CHANGED_MARKER}{note}"


def ruled_note(finding_text):
    """The note after the marker in a finding's text, or None when the text carries none."""
    _before, marker, note = finding_text.partition(CHANGED_MARKER)
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
