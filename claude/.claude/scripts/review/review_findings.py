"""Reading a reviewer's output: its Fix, Ask and Nit sections, the file:line, class and title of one finding, and the
merge of findings that name the same code."""

import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review")]
import handback

UNLOCATED = "unlocated"
FINDING_CLASS_TAG = re.compile(r"\[(" + "|".join(map(re.escape, handback.CLASSES)) + r")\]", re.I)
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)
TAGGED_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+`?(fix|ask|nit)`?\s*:\s*(.+)$", re.I)
CODE_TOKEN = re.compile(r"`([^`]+)`")
FINDING_FILE = re.compile(r"([\w./-]+\.\w+):(\d+)")


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


def finding_file(line):
    match = FINDING_FILE.search(line)
    return (match.group(1), int(match.group(2))) if match else ("", 0)


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
