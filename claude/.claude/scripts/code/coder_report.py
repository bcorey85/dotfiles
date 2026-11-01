"""Reading a coder hand-back report: the plan-impact block, the open questions, the eng-spec marker, and the why and
behavior notes."""
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils

OPEN_QUESTIONS_LINE = re.compile(r"^[ \t>*`_-]*OPEN QUESTIONS[*`_]*:[*`_]*[ \t]*(.*)$", re.M)
UNREADABLE_QUOTE_LIMIT = 120


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


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]
