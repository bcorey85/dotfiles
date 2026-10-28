"""The review loop's reading of reviewer text: the Fix/Ask/Nit sections of a review, a finding's file:line, class
tag and title, and the merge of findings that name the same code."""

import json
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback

UNLOCATED = "unlocated"

# A reviewer ask that says the fix would change the approved plan. An ask may open with its file:line and its
# bracketed tags, in either order.
PLAN_CHANGE_MARK = re.compile(r"(?:(?:`?[\w./-]+\.\w+:\d+`?|\[[\w-]+\])[\s—\N{EN DASH}:-]*)*plan[-_ ]?impact", re.I)
PLAN_CHANGE_YES = re.compile(r"plan[-_ ]?impact:\s*yes\s*$", re.I | re.M)
# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`.
ASK_CHANGE_MARK = re.compile(r"\bchange:", re.I)
FINDING_CLASS_TAG = re.compile(r"\[(" + "|".join(map(re.escape, handback.CLASSES)) + r")\]", re.I)
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)


def section(text, name):
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", text, re.S | re.M | re.I)
    return match.group(1).strip() if match else None


def review_section_findings(block):
    if not block:
        return []
    found = []
    for line in block.splitlines():
        stripped = re.sub(r"^\s*(?:[-*]+|\d+[.)])\s+", "", line).strip()
        if not stripped:
            continue
        if re.fullmatch(r"\[?(none|n/a|omitted|empty)[^\]]*\]?\.?", stripped, re.I):
            continue
        if ASSESSMENT_LINE.match(stripped):
            continue
        found.append(stripped)
    return found


TAGGED_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+`?(fix|ask|nit)`?\s*:\s*(.+)$", re.I)


def parse_tagged_bullets(text):
    """Reviewers that tag each bullet with its disposition (the test reviewer) instead of using Fix/Ask/Nit sections."""
    found = {"fix": [], "ask": [], "nit": []}
    for line in text.splitlines():
        match = TAGGED_BULLET.match(line)
        if match:
            found[match.group(1).lower()].append(match.group(2).strip())
    if not any(found.values()):
        return None
    return {**found, "assessment": ""}


def parse_review(text):
    fix, ask, nit = section(text, "Fix"), section(text, "Ask"), section(text, "Nit")
    if fix is None and ask is None and nit is None:
        return parse_tagged_bullets(text)
    assessment = re.search(r"Overall Assessment\W*\s*:?\W*\s*([A-Z][A-Z ]+[A-Z])", text)
    return {"fix": review_section_findings(fix), "ask": review_section_findings(ask),
            "nit": review_section_findings(nit),
            "assessment": assessment.group(1).strip() if assessment else ""}


def last_json_object(reply, keys):
    """The last JSON object in a reply that holds any of `keys`, or None. Decodes from each "{" back to front, because
    prose before the object can hold braces of its own ("{CUBE}")."""
    decoder = json.JSONDecoder()
    brace_positions = [match.start() for match in re.finditer(r"\{", reply)]
    for position in reversed(brace_positions):
        try:
            parsed, _ = decoder.raw_decode(reply, position)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and any(key in parsed for key in keys):
            return parsed
    return None


CODE_TOKEN = re.compile(r"`([^`]+)`")


def identifiers(finding):
    """Backticked names in a finding that are neither a file path nor a file:line pointer."""
    names = set()
    for token in CODE_TOKEN.findall(finding):
        if "/" in token or re.search(r":\d", token) or (re.search(r"\.\w{1,4}$", token) and "(" not in token):
            continue
        names.add(token)
    return names


def merge_findings(findings):
    """One list for the coder: a finding that names the same file and a shared identifier as an earlier one is
    folded into it."""
    merged = []
    for finding in findings:
        path = finding_file(finding)[0]
        names = identifiers(finding)
        home = next((index for index, kept in enumerate(merged)
                     if finding_file(kept)[0] == path and names & identifiers(kept) and path), None)
        if home is None:
            merged.append(finding)
        else:
            merged[home] += f" Also reported: {finding}"
    return merged


FINDING_FILE = re.compile(r"([\w./-]+\.\w+):(\d+)")


def finding_file(line):
    match = FINDING_FILE.search(line)
    return (match.group(1), int(match.group(2))) if match else ("", 0)


def names_absent_file(repo, tree_paths, finding):
    """True when the finding's file:line names a path that is not on disk and matches no path git lists."""
    path = finding_file(finding)[0]
    if not path or (pathlib.Path(repo) / path).exists():
        return False
    return not any(known == path or known.endswith("/" + path) for known in tree_paths)


def absent_file_split(repo, tree_paths, review):
    """(the review without its findings on a file neither on disk nor in git, those findings). A plan-change ask
    stays: it is about the plan, not the file."""
    kept, absent = {}, []
    for disposition in ("fix", "ask", "nit"):
        kept[disposition] = []
        for item in review[disposition]:
            if names_absent_file(repo, tree_paths, item) and not PLAN_CHANGE_MARK.match(item):
                absent.append(item)
            else:
                kept[disposition].append(item)
    return {**review, **kept}, absent


def finding_class(line):
    """The class the reviewer tagged the finding with, which the tag rule puts right after the file:line; `other` when
    it tagged none."""
    located = FINDING_FILE.search(line)
    match = FINDING_CLASS_TAG.search(line, located.end() if located else 0) or FINDING_CLASS_TAG.search(line)
    return match.group(1).lower() if match else "other"


def finding_title(line):
    """The finding's text with its file:line and bracketed tags taken out, lowercased, punctuation folded to spaces.
    A refile keeps it when the coder's edit moves the line."""
    title = re.sub(r"`?" + FINDING_FILE.pattern + r"`?", " ", line)
    title = re.sub(r"\[[\w-]+\]", " ", title)
    return re.sub(r"\W+", " ", title).strip().lower()
