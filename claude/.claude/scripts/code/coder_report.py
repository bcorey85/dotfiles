"""Reading a coder hand-back report: the plan-impact block, the open questions, the eng-spec marker, the why and
behavior notes, and the issue skips and the issues that cover them."""
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils

OPEN_QUESTIONS_LINE = re.compile(r"^[ \t>*`_-]*OPEN QUESTIONS[*`_]*:[*`_]*[ \t]*(.*)$", re.M)
ALREADY_APPLIED_MARKER = "ALREADY APPLIED"
SKIPPED_MARKER = "SKIPPED"
UNREADABLE_QUOTE_LIMIT = 120
COVERING_ISSUE = re.compile(
    r"\b(?:(?:fixed|done|covered|applied|handled|addressed)\s+(?:with|by|in|under)\s+(?:issue\s+|#)"
    r"|(?:same as|duplicate of)\s+(?:issue\s+|#)?)(\d+)\b", re.IGNORECASE)


def open_questions(report):
    # The strings of the report's `OPEN QUESTIONS: <JSON list of strings>` line. `none` or no such line means none. Any
    # other value that is not a JSON list of strings comes back as one flagged item. Only the first such line is read.
    found = OPEN_QUESTIONS_LINE.search(report)
    if not found:
        return []
    value = found.group(1).strip()
    if value.lower() == "none":
        return []
    questions = script_utils.json_string_list(value)
    if questions is not None:
        return questions
    quoted = script_utils.one_line(value, UNREADABLE_QUOTE_LIMIT)
    return [f"the OPEN QUESTIONS line could not be read as a JSON list of strings: {quoted}"]


PLAN_IMPACT_BLOCK_HEADER = "PLAN-IMPACT:\n"
PLAN_IMPACT_HEADER = re.compile(r"^[ \t>*`_-]*PLAN-IMPACT[*`_]*:?[*`_]*[ \t]*$")
PLAN_IMPACT_KEY = re.compile(r"^[ \t>*`_-]*(?:assumed|found|changes|acceptance_criteria|cause)[*`_]*:", re.I)


def plan_impact_body(lines_after_header):
    # The indented lines, or lines that start with one of the three keys, under a PLAN-IMPACT header. Blank lines may
    # sit between the header and the first line.
    body = []
    for later in lines_after_header:
        if not later.strip():
            if body:
                break
            continue
        if later[0] in " \t":
            body.append(later.rstrip())
        elif PLAN_IMPACT_KEY.match(later):
            body.append("  " + later.strip())
        else:
            break
    return body


def plan_impact_block(report):
    # The block is the header line `PLAN-IMPACT:` (bold or backticked is fine) and the lines under it.
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if not PLAN_IMPACT_HEADER.match(line):
            continue
        body = plan_impact_body(lines[index + 1:])
        if body:
            return PLAN_IMPACT_BLOCK_HEADER + "\n".join(body)
    if re.search(r"^PLAN-IMPACT:\s*yes\s*$", report, re.M):
        return "PLAN-IMPACT: yes (block not found in the report; read the report)"
    return None


def has_plan_impact_block(report):
    # True when the report holds a found block, not the `PLAN-IMPACT: yes (block not found…)` fallback.
    block = plan_impact_block(report)
    return block is not None and block.startswith(PLAN_IMPACT_BLOCK_HEADER)


ENG_SPEC_MARKER_LINE = re.compile(r"^[ \t>*`_-]*RECOMMEND[*`_]*:[ \t]*/?eng-spec[*`_.]*[ \t]*$", re.M | re.I)


def recommends_eng_spec(report):
    # Only the marker line the coder brief names escalates; a mention of /eng-spec in free text does not.
    return bool(ENG_SPEC_MARKER_LINE.search(report))


def why_by_file(report):
    grouped = {}
    for match in re.finditer(r"^WHY:\s*`?(\S+?)`?(?::|\s+)(\d+-\d+)\s*[—-]+\s*(.+)$", report, re.M):
        grouped.setdefault(match.group(1), []).append({"lines": match.group(2), "note": match.group(3).strip()})
    return grouped


def covered_issue(reason, number, issue_count):
    """The other listed issue a skip reason names as the one that covers it (`fixed with issue <m>`, `same as #<m>`,
    `duplicate of <m>`), or None. A bare mention of an issue is no cover."""
    for match in COVERING_ISSUE.finditer(reason):
        covering = int(match.group(1))
        if covering != number and 1 <= covering <= issue_count:
            return covering
    return None


def issue_marker_lines(report, word, issue_count):
    """Issue number -> the first `<word> <n>: ...` line of the report that names it, for numbers that name a listed
    issue. `word` is the marker's words (`SKIPPED`, `ALREADY APPLIED`); a `SKIPPED small <n>` line is no match."""
    pattern = re.compile(rf"\s*[-*]?\s*(?:\*\*|`)?{re.escape(word)} (\d+)(?:\*\*|`)?:")
    lines = {}
    for line in report.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        number = int(match.group(1))
        if 1 <= number <= issue_count:
            lines.setdefault(number, line.strip())
    return lines


def already_applied_issues(report, issue_count):
    """Issue number -> the coder's `ALREADY APPLIED <n>: <where>` line, for the issues the coder reported as already
    in the tree, for numbers that name a listed issue."""
    return issue_marker_lines(report, ALREADY_APPLIED_MARKER, issue_count)


def skipped_issues(report, issue_count):
    """Issue number -> the coder's `SKIPPED <n>: <reason>` line, for numbers that name a listed issue. A `SKIPPED
    small <n>` line is a small item's, never an issue's. An issue whose reason names another listed issue as the one
    that covers it is fixed, so it is no skip, when its chain of covering issues ends at an issue the coder did not
    skip (see cover_chain_ends_fixed)."""
    skips = issue_marker_lines(report, SKIPPED_MARKER, issue_count)
    coverings = {number: covered_issue(line.split(":", 1)[1], number, issue_count)
                 for number, line in skips.items()}
    fixed = [number for number, covering in coverings.items()
             if covering is not None and cover_chain_ends_fixed(covering, skips, coverings)]
    for number in fixed:
        del skips[number]
    return skips


def cover_chain_ends_fixed(covering, skips, coverings):
    """Whether following covering issues from `covering` ends at an issue the coder did not skip. A chain that ends
    at a skip with no cover, or loops, is not fixed."""
    seen = set()
    current = covering
    while current not in seen:
        seen.add(current)
        if current not in skips:
            return True

        next_cover = coverings[current]
        if next_cover is None:
            return False

        current = next_cover
    return False


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]
