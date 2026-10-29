"""The review loop's reading of reviewer text: the Fix/Ask/Nit sections of a review, a finding's file:line, class
tag and title, and the merge of findings that name the same code."""

import json
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback
import plan_format
import script_utils
from plan_format import PLAN_CHANGE_MARK

UNLOCATED = handback.UNLOCATED

PLAN_CHANGE_YES = re.compile(r"plan[-_ ]?impact:\s*yes\s*$", re.I | re.M)
# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`.
ASK_CHANGE_MARK = re.compile(r"\bchange(?:\s+if\s+accepted)?:", re.I)
ITEM_MARKER = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
ITEM_MARKER_STRIP = re.compile(r"^\s*(?:[-*]+|\d+[.)])\s+")
FINDING_CLASS_TAG = re.compile(r"\[(" + "|".join(map(re.escape, handback.CLASSES)) + r")\]", re.I)
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)


def section(text, name):
    # The section body keeps the indent of its first line: review_section_findings compares marker indents.
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", text, re.S | re.M | re.I)
    if not match:
        return None
    return re.sub(r"\A(?:[ \t]*\n)+", "", match.group(1)).rstrip()


def indent_of(line):
    return len(line) - len(line.lstrip())


def review_section_findings(block):
    if not block:
        return []
    # A bullet or numbered marker at the first marker's indent starts an item. A marker indented deeper is a
    # sub-bullet, and it and any other line, after a blank line too, continue the item before it.
    marker_lines = [line for line in block.splitlines() if ITEM_MARKER.match(line)]
    item_indent = indent_of(marker_lines[0]) if marker_lines else 0

    found = []
    for line in block.splitlines():
        starts_item = bool(ITEM_MARKER.match(line)) and indent_of(line) <= item_indent
        stripped = ITEM_MARKER_STRIP.sub("", line).strip()
        if not stripped:
            continue
        if re.fullmatch(r"\[?(none|n/a|omitted|empty)[^\]]*\]?\.?", stripped, re.I):
            continue
        if ASSESSMENT_LINE.match(stripped):
            continue
        if starts_item or not found:
            found.append(stripped)
            continue
        found[-1] = f"{found[-1]} {stripped}"
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


MERGED_SEPARATOR = " Also reported: "
REFILE_SIMILARITY = 0.8


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
            merged[home] += f"{MERGED_SEPARATOR}{finding}"
    return merged


def near_title(title, other_title):
    """Whether two finding titles are the same or near."""
    return script_utils.text_similarity(title, other_title) >= REFILE_SIMILARITY


def same_finding(location, title, other_location, other_title):
    """Whether two findings in the same file name the same issue: a near title when both have one, else the same
    line."""
    if location[0] != other_location[0]:
        return False
    if title and other_title:
        return near_title(other_title, title)
    return location[1] == other_location[1]


def unreported_parts(fixed_item, open_fixes):
    """The findings folded into a fixed entry that no open fix finding reports again. An open fix reports a part
    again when it names the same file and, when both have a title, the same or a near title, or else the same line.
    A part with no file is never reported again."""
    open_parts = [part for item in open_fixes for part in item.split(MERGED_SEPARATOR)]
    open_located = [(finding_file(part), finding_title(part)) for part in open_parts]
    kept = []
    for fixed_part in fixed_item.split(MERGED_SEPARATOR):
        location = finding_file(fixed_part)
        title = finding_title(fixed_part)
        reported = bool(location[0]) and any(same_finding(location, title, open_location, open_title)
                                             for open_location, open_title in open_located)
        if not reported:
            kept.append(fixed_part)
    return kept


def reported_again(fixed_item, open_fixes):
    """Whether an open fix finding reports again any finding folded into a fixed entry."""
    fixed_parts = fixed_item.split(MERGED_SEPARATOR)
    kept = unreported_parts(fixed_item, open_fixes)
    return len(kept) < len(fixed_parts)


def still_fixed(fixed_items, open_fixes):
    """The fixed entries with the findings that open fix findings report again taken out; an entry with none left
    is dropped."""
    kept = []
    for item in fixed_items:
        parts = unreported_parts(item, open_fixes)
        if parts:
            kept.append(MERGED_SEPARATOR.join(parts))
    return kept


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


def plan_change_items(items):
    """The items that say the fix would change the approved plan."""
    return [item for item in items if PLAN_CHANGE_MARK.match(item)]


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


RULING_HEADINGS = (plan_format.DEVIATIONS_HEADING, "Constraints")
RULED_PLAN_NOTE = " — a recorded plan ruling covers this line; the fix would undo it"


def ruled_plan_line(plan_lines, line_number):
    """True when the plan line sits under a ruling heading, or holds a backticked value a ruling line holds."""
    ruling_indexes = [index for heading in RULING_HEADINGS
                      for index in script_utils.heading_section_indexes(plan_lines, heading)]
    target_index = line_number - 1
    if target_index in ruling_indexes:
        return True
    if not 0 <= target_index < len(plan_lines):
        return False

    ruled_values = {value for index in ruling_indexes for value in re.findall(r"`([^`]+)`", plan_lines[index])}
    target_text = plan_lines[target_index]
    return any(value in target_text for value in ruled_values)


def ruled_plan_split(repo, plan, fixes):
    """(the fixes, the fixes that target a plan line a recorded ruling covers, turned into asks)."""
    plan_path = pathlib.Path(repo) / plan
    if not plan or not plan_path.is_file():
        return fixes, []

    plan_lines = plan_path.read_text().splitlines()
    kept, ruled = [], []
    for item in fixes:
        path, line = finding_file(item)
        if path == plan and ruled_plan_line(plan_lines, line):
            ruled.append(item + RULED_PLAN_NOTE)
        else:
            kept.append(item)
    return kept, ruled


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
