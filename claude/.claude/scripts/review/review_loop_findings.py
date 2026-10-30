"""The review loop's reading of reviewer text: the Fix/Ask/Nit sections of a review as finding records, and the merge
of findings that name the same code."""

import json
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback
import plan_format
import script_utils
from finding_record import combine, parse_finding
from plan_format import PLAN_CHANGE_MARK
from source_text import indent_of

UNLOCATED = handback.UNLOCATED

PLAN_CHANGE_YES = re.compile(r"plan[-_ ]?impact:\s*yes\s*$", re.I | re.M)
# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`.
ASK_CHANGE_MARK = re.compile(r"\bchange(?:\s+if\s+accepted)?:", re.I)
ITEM_MARKER = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
ITEM_MARKER_STRIP = re.compile(r"^\s*(?:[-*]+|\d+[.)])\s+")
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)
NONE_LINE = re.compile(r"\[?(none|n/a|omitted|empty)[^\]]*\]?\.?", re.I)
# A section's opening none line: a none word that ends its sentence, as in "None." or "None. What I checked:".
NONE_OPENING = re.compile(r"[\[(*_`]*(?:none|n/a|omitted|empty)[\])*_`]*"
                          r"(?:[.:;,!]|\s+[\N{EM DASH}\N{EN DASH}-]|$)", re.I)
# A finding's head: its file:line first, after an optional [blocker] tag and bold markup.
FINDING_HEAD = re.compile(rf"(?:{script_utils.BLOCKER_TAG_PATTERN}\s*)?[*_]*" + script_utils.PATH_LINE.pattern,
                          re.I)


def section(text, name):
    # The section body keeps the indent of its first line: review_section_findings compares marker indents.
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", text, re.S | re.M | re.I)
    if not match:
        return None
    return re.sub(r"\A(?:[ \t]*\n)+", "", match.group(1)).rstrip()


def is_bare_finding_head(line):
    return not ITEM_MARKER.match(line) and bool(FINDING_HEAD.match(line.strip()))


def item_start_lines(lines):
    """The indexes of the section lines that start an item. A finding written as a paragraph opens with a bare
    file:line, and the bullets under it are its points: when the section opens with one, each bare file:line line at
    its indent starts an item. Otherwise a bullet or numbered marker at the first marker's indent starts one. A marker
    indented deeper is a sub-bullet, and it and any other line, after a blank line too, continue the item before it."""
    first_line = next(line for line in lines if line.strip())
    if is_bare_finding_head(first_line):
        return {index for index, line in enumerate(lines)
                if is_bare_finding_head(line) and indent_of(line) <= indent_of(first_line)}

    marker_indents = [indent_of(line) for line in lines if ITEM_MARKER.match(line)]
    item_indent = marker_indents[0] if marker_indents else 0
    return {index for index, line in enumerate(lines) if ITEM_MARKER.match(line) and indent_of(line) <= item_indent}


def review_section_findings(block):
    if not block:
        return []
    lines = block.splitlines()

    # A section that opens with a none line holds no finding: the lines after it are the reviewer's notes, such as
    # what it checked or why it flagged nothing.
    first_text = ITEM_MARKER_STRIP.sub("", next(line for line in lines if line.strip())).strip()
    if NONE_OPENING.match(first_text):
        return []

    starts = item_start_lines(lines)
    found = []
    for index, line in enumerate(lines):
        stripped = ITEM_MARKER_STRIP.sub("", line).strip()
        if not stripped:
            continue
        if NONE_LINE.fullmatch(stripped):
            continue
        if ASSESSMENT_LINE.match(stripped):
            continue
        if index in starts or not found:
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


def parse_review_texts(text):
    fix, ask, nit = section(text, "Fix"), section(text, "Ask"), section(text, "Nit")
    if fix is None and ask is None and nit is None:
        return parse_tagged_bullets(text)
    assessment = re.search(r"Overall Assessment\W*\s*:?\W*\s*([A-Z][A-Z ]+[A-Z])", text)
    return {"fix": review_section_findings(fix), "ask": review_section_findings(ask),
            "nit": review_section_findings(nit),
            "assessment": assessment.group(1).strip() if assessment else ""}


def finding_records(review_texts):
    """The review with each finding's text parsed into a record."""
    return {**review_texts, **{disposition: [parse_finding(item) for item in review_texts[disposition]]
                               for disposition in ("fix", "ask", "nit")}}


def parse_review(text):
    """The review's {fix, ask, nit: [finding records], assessment}, or None when the text has no findings layout."""
    review_texts = parse_review_texts(text)
    if review_texts is None:
        return None
    return finding_records(review_texts)


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


# How much of the first unparsable reply the retry note quotes.
RETRY_ERROR_CHARS = 200


def reply_with_one_retry(claude_call, role, prompt, repo, out, keys, shape, **options):
    """The parsed JSON object of a model reply that holds any of `keys`. A reply with none is retried once under
    "<role>-retry", so the retry has its own row in calls.jsonl; a second miss raises ValueError."""
    reply = claude_call(role, prompt, repo, out, **options)
    parsed = last_json_object(reply, keys)
    if parsed is not None:
        return parsed

    error = f"the {role} reply holds no {shape} object: {reply!r}"
    retry_note = f"A previous reply to this prompt could not be parsed: {error[:RETRY_ERROR_CHARS]}"
    retry_prompt = prompt + f"\n\n{retry_note}\nReply with the JSON object only."
    reply = claude_call(f"{role}-retry", retry_prompt, repo, out, **options)
    parsed = last_json_object(reply, keys)
    if parsed is None:
        raise ValueError(f"the {role} reply holds no {shape} object: {reply!r}")
    return parsed


REFILE_SIMILARITY = 0.8


def merge_findings(findings):
    """One list for the coder: a finding that names the same file and a shared identifier as an earlier one is
    folded into it."""
    merged = []
    for finding in findings:
        home = next((index for index, kept in enumerate(merged)
                     if kept.path == finding.path and finding.identifiers & kept.identifiers and finding.path), None)
        if home is None:
            merged.append(finding)
        else:
            merged[home] = combine([*merged[home].each_part, finding])
    return merged


def near_title(title, other_title):
    """Whether two finding titles are the same or near."""
    return script_utils.text_similarity(title, other_title) >= REFILE_SIMILARITY


def same_finding(finding, other):
    """Whether two findings in the same file name the same issue: a near title when both have one, else the same
    line."""
    if finding.path != other.path:
        return False
    if finding.title and other.title:
        return near_title(other.title, finding.title)
    return finding.line == other.line


def unreported_parts(fixed_item, open_fixes):
    """The findings folded into a fixed entry that no open fix finding reports again. An open fix reports a part
    again when it names the same file and, when both have a title, the same or a near title, or else the same line.
    A part with no file is never reported again."""
    open_parts = [part for item in open_fixes for part in item.each_part]
    kept = []
    for fixed_part in fixed_item.each_part:
        reported = bool(fixed_part.path) and any(same_finding(fixed_part, open_part) for open_part in open_parts)
        if not reported:
            kept.append(fixed_part)
    return kept


def reported_again(fixed_item, open_fixes):
    """Whether an open fix finding reports again any finding folded into a fixed entry."""
    kept = unreported_parts(fixed_item, open_fixes)
    return len(kept) < len(fixed_item.each_part)


def still_fixed(fixed_items, open_fixes):
    """The fixed entries with the findings that open fix findings report again taken out; an entry with none left
    is dropped."""
    kept = []
    for item in fixed_items:
        parts = unreported_parts(item, open_fixes)
        if parts:
            kept.append(combine(parts))
    return kept


def names_absent_file(repo, tree_paths, finding):
    """True when the finding's file:line names a path that is not on disk and matches no path git lists."""
    path = finding.path
    if not path or (pathlib.Path(repo) / path).exists():
        return False
    return not any(known == path or known.endswith("/" + path) for known in tree_paths)


def plan_change_items(items):
    """The items that say the fix would change the approved plan."""
    return [item for item in items if PLAN_CHANGE_MARK.match(item.text)]


def absent_file_split(repo, tree_paths, review):
    """(the review without its findings on a file neither on disk nor in git, those findings). A plan-change ask
    stays: it is about the plan, not the file."""
    kept, absent = {}, []
    for disposition in ("fix", "ask", "nit"):
        kept[disposition] = []
        for item in review[disposition]:
            if names_absent_file(repo, tree_paths, item) and not PLAN_CHANGE_MARK.match(item.text):
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
        if item.path == plan and ruled_plan_line(plan_lines, item.line):
            ruled.append(parse_finding(item.text + RULED_PLAN_NOTE))
        else:
            kept.append(item)
    return kept, ruled
