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
    """A finding. `path` is "" and `line` 0 when the text names no file:line. A merged finding takes its path, line,
    class and title from its first part, and holds every part, each with its own, in `parts`; a plain finding has
    no parts."""

    text: str
    path: str
    line: int
    finding_class: str
    title: str
    identifiers: frozenset
    parts: tuple = ()

    @property
    def each_part(self):
        """The findings this one stands for: its parts when merged, else itself."""
        return self.parts or (self,)


def code_identifiers(text):
    """Backticked names in a finding that are neither a file path nor a file:line pointer."""
    names = set()
    for token in script_utils.backticked_spans(text):
        if "/" in token or re.search(r":\d", token) or (re.search(r"\.\w{1,4}$", token) and "(" not in token):
            continue
        names.add(token)
    return frozenset(names)


def parse_finding(text):
    """The record of one finding's text: its file:line, the class the reviewer tagged it with, its title and the
    code names it mentions."""
    located = script_utils.PATH_LINE.search(text)
    path, line = script_utils.split_location(located.group(1)) if located else ("", 0)

    # The tag rule puts the class right after the file:line; `other` when the reviewer tagged none.
    class_tag = FINDING_CLASS_TAG.search(text, located.end() if located else 0) or FINDING_CLASS_TAG.search(text)
    finding_class = class_tag.group(1).lower() if class_tag else "other"

    # The title is the text with its file:line and bracketed tags taken out, lowercased, punctuation folded to
    # spaces. A refile keeps it when the coder's edit moves the line.
    title = script_utils.PATH_LINE.sub(" ", text)
    title = re.sub(r"\[[\w-]+\]", " ", title)
    title = re.sub(r"\W+", " ", title).strip().lower()

    return Finding(text, path, line, finding_class, title, code_identifiers(text))


def combine(parts):
    """One finding from its parts, in order: the part itself for a single part, else a merged finding whose text
    joins the parts' texts and whose identifiers are the union of the parts' names."""
    first = parts[0]
    if len(parts) == 1:
        return first

    text = MERGED_SEPARATOR.join(part.text for part in parts)
    identifiers = frozenset().union(*(part.identifiers for part in parts))
    return Finding(text, first.path, first.line, first.finding_class, first.title, identifiers, tuple(parts))
