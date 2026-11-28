"""One reviewer finding, parsed once. The review loop passes these records around instead of re-reading the finding's
text with a regex at each step."""

import dataclasses
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback
import script_utils

FINDING_CLASS_TAG = re.compile(r"\[(" + "|".join(map(re.escape, handback.CLASSES)) + r")\]", re.I)
MERGED_SEPARATOR = " Also reported: "


@dataclasses.dataclass(frozen=True)
class Finding:
    """A finding. `path` is "" when the text names no location; `line` is 0 when the location has no exact line
    number (a bare path, or an approximate `~` line). A merged finding takes its path, line,
    class and title from its first part, and holds every part, each with its own, in `parts`; a plain finding has
    no parts. `bare` is True when the location is a path with no line part."""

    text: str
    path: str
    line: int
    finding_class: str
    title: str
    identifiers: frozenset
    parts: tuple = ()
    bare: bool = False

    @property
    def each_part(self):
        """The findings this one stands for: its parts when merged, else itself."""
        return self.parts or (self,)


def code_identifiers(text):
    """Backticked names in a finding that are neither a file path nor a file:line pointer."""
    names = set()
    for token in script_utils.backticked_spans(text):
        # Skips a `path:~N` pointer; the `:\d` check below skips an exact line.
        if ":" in token and script_utils.LOCATION_ALONE.fullmatch(token):
            continue
        if "/" in token or re.search(r":\d", token) or (re.search(r"\.\w{1,4}$", token) and "(" not in token):
            continue
        names.add(token)
    return frozenset(names)


def parse_finding(text):
    """The record of one finding's text: its location, the class the reviewer tagged it with, its title and the
    code names it mentions."""
    located = script_utils.first_location(text)
    path, line = (located.path, located.line) if located else ("", 0)

    # The tag rule puts the class right after the location; `other` when the reviewer tagged none.
    # A tag inside a quoted span is a quotation, not the reviewer's tag.
    tag_start = located.end if located else 0
    tag_after_location = script_utils.first_unquoted_match(FINDING_CLASS_TAG, text, tag_start)
    class_tag = tag_after_location or script_utils.first_unquoted_match(FINDING_CLASS_TAG, text)
    finding_class = class_tag.group(1).lower() if class_tag else "other"

    # The title is the text with its exact path:line tokens and bracketed tags taken out, lowercased, punctuation
    # folded to spaces. An approximate pointer (`a.py:~40`) stays in it, so a refile keeps the title only when the
    # coder's edit moves an exact line. A bare path stays in it too and does not break the match.
    title = script_utils.PATH_LINE.sub(" ", text)
    title = re.sub(r"\[[\w-]+\]", " ", title)
    title = re.sub(r"\W+", " ", title).strip().lower()

    bare = bool(located and located.bare)
    return Finding(text, path, line, finding_class, title, code_identifiers(text), bare=bare)


def combine(parts):
    """One finding from its parts, in order: the part itself for a single part, else a merged finding whose text
    joins the parts' texts and whose identifiers are the union of the parts' names."""
    first = parts[0]
    if len(parts) == 1:
        return first

    text = MERGED_SEPARATOR.join(part.text for part in parts)
    identifiers = frozenset().union(*(part.identifiers for part in parts))
    return Finding(
        text, first.path, first.line, first.finding_class, first.title, identifiers, parts=tuple(parts), bare=first.bare
    )


def identity(finding):
    """What names a finding across rounds: its file, exact line and class. A finding with no path or no exact line is
    its own identity, so two unlocated findings never merge."""
    if not finding.path or not finding.line:
        return finding
    return (finding.path, finding.line, finding.finding_class)


def unseen(recorded, findings):
    """The findings of `findings` that `recorded` does not already hold under the same identity, each identity
    once. A later round that raises the same file, line and class again adds nothing."""
    seen = {identity(finding) for finding in recorded}
    fresh = []
    for finding in findings:
        key = identity(finding)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(finding)
    return fresh
