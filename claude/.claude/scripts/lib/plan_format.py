"""plan_format.py: the one reader of a plan's phase sections, its Phase Status list and its `#### Manual Verification`
sections.

Installed in scripts/lib beside script_utils.py. A plan file is text a person or a model wrote, so the
reader stops on any line it does not know and names the file and the line.

Section grammar, from every real plan under ~/dev/*/docs/{plans,eng-specs}:
  heading   `### Manual Verification` or `#### Manual Verification`, optionally followed by a qualifier such as
            `(human-only, Brandon):`. The same words at any other heading level are an error.
  item      a list entry at column 0: `- [ ] text`, `- [x] text` (the template form), `- text`, `* text`, `1. text`.
            Indented lines below it (sub-bullets, wrapped text, numbered steps) belong to it.
  marker    a line that opens with `N/A` (bare or as a plain bullet): the phase has no manual items.
  prose     a line at column 0 that is not a list entry (an intro such as "In a temp root:", "Expected: ...").
  end       the next heading of the section's own level or a higher one, a `---` rule, or the end of the file.
Anything else fails: a fenced block, a table, a quote, an HTML comment, an indented line with no item above it, or a
list item under a deeper sub-heading inside the section (it would be read as a manual item).
A phase stays open across its Success Criteria, Automated Verification and Manual Verification headings, whatever
their level.

Phase Status grammar: `- [ ] Phase <id>: <title>` is open, `- [x] ...` is done, and `- [-] ...` is moved to another
ticket. A moved line says `moved to <KEY>` (a ticket key such as LED-16), and the plan's `## Plan Deviations` section
holds a line that names the phase (`Phase <id>` or `P<id>`) and the ticket key. The reader checks that the line exists,
never who signed it. A moved phase is neither done nor open, and it needs no `## Phase <id>` section: a move may take
the section to the new ticket.
"""
import datetime
import json
import pathlib
import re

import script_utils
import source_text

# A `path/to/file.ext` or a repo-root `file.ext` in backticks, with an optional :line or :start-end suffix inside the
# ticks. Prose holds many bare names that name no file (`os.path`, `row.ts`), so most readers take a bare name only from
# a `**File**:` entry or when the repo holds it (named_paths). The one reader that takes every backticked name is
# expected_red.section_paths (own-path exclusion).
PATH_IN_BACKTICKS = re.compile(r"`([\w.@+-]+(?:/[\w.@\[\]()+-]+)*\.\w+)(?::\d+(?:-\d+)?)?`")
FILE_ENTRY = re.compile(r"^\s*(?:[-*]\s+)?\*\*Files?\*\*:?")
TOP_LEVEL_BULLET = re.compile(r"^[-*]\s+")
PHASE_ID = r"(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*"
# "same as Phase N" in a phase's text: the phase reuses that phase's steps.
SAME_AS_PHASE = re.compile(rf"\bsame as (?:the )?Phase ({PHASE_ID})", re.IGNORECASE)
PHASE_HEADING = re.compile(rf"^(#{{2,4}})\s+Phase\s+({PHASE_ID})(?![A-Za-z0-9])")
MANUAL_HEADING = re.compile(r"^(#{1,6})\s+manual verification\b(.*)$", re.I)
SUCCESS_GROUP_HEADING = re.compile(r"^#{1,6}\s+(?:success criteria|automated verification|manual verification)\b", re.I)
LIST_ENTRY = re.compile(r"^(?:[-*]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.*)$")
NOT_APPLICABLE = re.compile(r"^(?:[-*]\s+)?N/A\b", re.I)
FOREIGN_START = ("|", ">", "<")
SECTION_LEVELS = (3, 4)
MID_EDIT_KINDS = {"duplicate-id", "missing-section", "section-without-status"}
HUMAN_ONLY_MARK = "human-only"
AGENT_VERIFIED_MARK = "agent-verified"


PHASE_STATUS_LINE = re.compile(rf"^[-*]\s+\[( |x|X|-)\]\s+Phase\s+({PHASE_ID})\s*[:.—–-]\s*(.*)$")
MOVED_MARK = "-"
MOVED_TARGET = re.compile(r"(?i:moved to)\s+([A-Z][A-Z0-9]*-\d+)(?![A-Za-z0-9])")
DEVIATIONS_HEADING = "Plan Deviations"
SESSION_RULING_OWNER = "the session, not the user"
# A reviewer ask that says the fix would change the approved plan. An ask may open with its file:line and its
# bracketed tags, in either order. `PLAN-IMPACT: none`, or a bare `no` ended by punctuation or the line, says the
# plan holds, so it is no plan change; `PLAN-IMPACT: no index on ...` still is one.
LINE_RANGE = r"\d+(?:[-\N{EN DASH}]\d+)?(?:,\d+(?:[-\N{EN DASH}]\d+)?)*"
PLAN_CHANGE_MARK = re.compile(
    rf"(?:(?:`?[\w./-]+\.\w+:{LINE_RANGE}`?|\[[\w-]+\])[\s—\N{{EN DASH}}:-]*)*plan[-_ ]?impact"
    r"(?![*`_]*:[ \t*`_]*(?:none\b|no(?:[.;,)*`_]|[ \t]*$)))", re.I | re.M)
PLAN_IMPACT_BLOCK_HEADER = "PLAN-IMPACT:\n"
# A PLAN-IMPACT's `acceptance_criteria:` line: `none`, or the criteria the change would alter.
AC_CHANGE_LINE = re.compile(r"acceptance[_ ]criteria[*`_]*:[ \t*`_]*([^;\n]*)", re.I)
PLAN_IMPACT_OPENING = re.compile(r"plan[-_ ]?impact(?![*`_]*:[ \t*`_]*yes\b)", re.I)
PLAN_IMPACT_CAUSE = re.compile(r"^[ \t>*`_-]*cause[*`_]*:[ \t*`_]*(.*?)[ \t*`_]*$", re.I | re.M)
# plan: the plan and the code disagree. toolkit: a toolkit gate or script is at fault and nothing in the plan is wrong.
PLAN_CAUSE = "plan"
TOOLKIT_CAUSE = "toolkit"
PLAN_IMPACT_CAUSES = (PLAN_CAUSE, TOOLKIT_CAUSE)
# A packet's cause for a block that names none where one is required; never a cause a block can write.
NO_CAUSE_LINE = "no-cause-line"
BELOW_CRITERIA_RULING = ("No acceptance criterion changes, so the code wins: the plan follows the code. Adopted by "
                         "rule; no one was asked.")
PLAN_IMPACT_HEADER_WORD = re.compile(r"[*`_]*plan[-_ ]?impact[*`_]*[ \t]*:", re.I)
# The `acceptance_criteria:` clause with the marks and separators before it, so removing it leaves no stray dash.
AC_CHANGE_CLAUSE = re.compile(r"[\s;,—\N{EN DASH}-]*[*`_]*" + AC_CHANGE_LINE.pattern, re.I)
DEVIATION_RULING_PREFIX = "  The ruling: "
STATUS_ITEM_START = re.compile(r"^[-*]\s+\[")
RISK_MARK = re.compile(r"\(risk:\s*(low|high)\)", re.I)
GATE_CLAUSE = re.compile(r"—\s*gate:", re.IGNORECASE)


class PlanFormatError(Exception):
    """A line the grammar does not parse. The message starts with `name:line:`."""


class NoCriteriaHeadingError(PlanFormatError):
    """A ticket with no `## Acceptance*` or `## Requirements*` heading."""


def _duplicate_phase_failure(section_id, first_line, index):
    """The `duplicate-id` failure for a second section of one phase id."""
    return {"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {section_id} has two "
            f"sections, on line {first_line + 1} and line {index + 1}. Give "
            "each phase its own id."}


def _open_phase_section(lines, index, level, phase_heading):
    """A new phase section that starts at this heading and runs to the end of the plan until a later heading ends it."""
    title = lines[index][phase_heading.end():].lstrip(" :.—–-")
    return {"start": index, "level": level, "title": title, "end": len(lines)}


def _section_open_at_heading(current, level, line, index):
    """The open section after this heading: `current` with its end set at `index` and None when the heading ends it,
    else `current` unchanged."""
    if current is None or level > current["level"] or SUCCESS_GROUP_HEADING.match(line):
        return current
    current["end"] = index
    return None


def phase_spans(lines):
    """Every `Phase <id>` section of the plan in file order, as (id, {"start", "level", "title", "end"}) with 0-based
    line indexes, `end` exclusive, and the failures for ids that have two sections.

    A section runs to the next heading of its own level or a higher one, or to the next section. Its Success Criteria,
    Automated Verification and Manual Verification headings do not end it, whatever their level. A heading of an id
    that already has a section, deeper than the section it sits in (a `#### Phase <id> record` under `## Phase <id>`),
    is a note inside that section, not a second section. A second section of one id is a failure and is still
    returned."""
    fenced = script_utils.fenced_line_indexes(lines)
    spans = []
    failures = []
    first_lines = {}
    current = None

    for index, line in enumerate(lines):
        if index in fenced:
            continue
        heading = script_utils.MARKDOWN_HEADING.match(line)
        if not heading:
            continue

        level = len(heading.group(1))
        current = _section_open_at_heading(current, level, line, index)
        phase_heading = PHASE_HEADING.match(line)
        if not phase_heading:
            continue

        section_id = phase_heading.group(2)
        if current is not None and level > current["level"] and section_id in first_lines:
            continue
        if current is not None:
            current["end"] = index
        current = _open_phase_section(lines, index, level, phase_heading)
        spans.append((section_id, current))
        if section_id not in first_lines:
            first_lines[section_id] = index
            continue
        failures.append(_duplicate_phase_failure(section_id, first_lines[section_id], index))
    return spans, failures


def phase_section(lines, phase_id):
    """The first section of the phase with this exact id as {"start", "level", "title", "end"}, or None."""
    spans, _ = phase_spans(lines)
    return next((section for section_id, section in spans if section_id == phase_id), None)


def named_paths(text, repo_dir):
    """The file paths the text names in backticks, in order, once each: every path with a folder, and every bare
    `name.ext` that is a file at the root of repo_dir (a pathlib.Path)."""
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(text):
        path = match.group(1)
        if path in paths:
            continue
        if "/" not in path and not (repo_dir / path).is_file():
            continue
        paths.append(path)
    return paths


def file_entry_paths(plan_lines, section):
    """The paths a section's Changes Required entries name: every backticked path on a `**File**:` or `**Files**:`
    line, and the first one of each top-level bullet in the list under a `**Files**:` line that names none. A
    repo-root `name.ext` counts: the entry names it as a file."""
    if section is None:
        return set()

    fenced = script_utils.fenced_line_indexes(plan_lines)
    paths = set()
    in_list = False
    for index in range(section["start"], section["end"]):
        line = plan_lines[index]
        if index in fenced:
            in_list = False
            continue

        in_list = _collect_entry_paths(line, in_list, paths)
    return paths


def _collect_entry_paths(line, in_list, paths):
    """Add the paths this line names to `paths`, and return whether the next line is still in a `**Files**:` list."""
    line_paths = [match.group(1) for match in PATH_IN_BACKTICKS.finditer(line)]
    if FILE_ENTRY.match(line):
        paths.update(line_paths)
        return not line_paths
    if not in_list:
        return False
    if TOP_LEVEL_BULLET.match(line):
        paths.update(line_paths[:1])
        return True
    ends_list = line.strip() and not line[:1].isspace()
    return not ends_list


def required_structure(plan_lines):
    """What the plan requires a refactor to keep: {"files": every path its phases' Changes Required entries name,
    sorted, "deviations": the non-blank lines of its `## Plan Deviations` section, in file order}."""
    spans, _ = phase_spans(plan_lines)
    files = set()
    for _, section in spans:
        files |= file_entry_paths(plan_lines, section)
    deviation_indexes = script_utils.heading_section_indexes(plan_lines, DEVIATIONS_HEADING)
    deviations = [plan_lines[index] for index in deviation_indexes if plan_lines[index].strip()]
    return {"files": sorted(files), "deviations": deviations}


def phase_status_entries(lines, closing_skill):
    """The `- [ ] Phase <id>: <title>` lines under the `Phase Status` heading, in file order, and the failures for a
    list line that does not parse or an id listed twice. `closing_skill(title)` names the skill a closing phase runs,
    or None. Each entry is {"line", "done", "number", "title", "risk", "closing", "gate"}; "gate" is True when the
    title has a `— gate:` clause. "moved" is True for a `[-]` line
    and "movedTo" is the ticket key its `moved to <KEY>` names, or None; a moved phase is not "done". "open" is True
    for a phase that is neither done nor moved: the phases a run can still start. A `[-]` line with no
    `moved to <KEY>` is a failure and still returns its entry."""
    fenced = script_utils.fenced_line_indexes(lines)
    entries = []
    failures = []
    first_lines = {}
    in_status = False

    for index, line in enumerate(lines):
        if index in fenced:
            continue
        heading = script_utils.MARKDOWN_HEADING.match(line)
        if heading:
            in_status = heading.group(2).strip() == "Phase Status"
            continue
        if not in_status or not STATUS_ITEM_START.match(line):
            continue

        match = PHASE_STATUS_LINE.match(line)
        if not match:
            failures.append({"line": index + 1, "kind": "unparsed-line", "detail": f"{line.strip()!r}. Rewrite it as "
                             "`- [ ] Phase <id>: <title>`, or move it out of the section."})
            continue

        number = match.group(2)
        if number in first_lines:
            failures.append(_duplicate_status_failure(number, first_lines[number], index))
            continue
        first_lines[number] = index
        entry = _phase_status_entry(index, match, closing_skill)
        entries.append(entry)
        if entry["moved"] and entry["movedTo"] is None:
            failures.append(_moved_without_target_failure(index, number))
    return entries, failures


def _duplicate_status_failure(number, first_line, index):
    """The `duplicate-id` failure for a phase id listed twice in Phase Status."""
    return {"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {number} twice, on line "
            f"{first_line + 1} and line {index + 1}. Give each phase its own id."}


def _moved_without_target_failure(index, number):
    """The `moved-without-target` failure for a `[-]` line that names no ticket key."""
    return {"line": index + 1, "kind": "moved-without-target", "detail": f"Phase {number} is marked "
            "`[-]` (moved to another ticket) but the line does not say `moved to <KEY>`. Add the "
            "ticket key, for example `moved to LED-16`."}


def _phase_status_entry(index, match, closing_skill):
    """The entry dict for one parsed Phase Status line."""
    title = match.group(3)
    risk = RISK_MARK.search(title)
    is_moved = match.group(1) == MOVED_MARK
    target = MOVED_TARGET.search(title) if is_moved else None
    is_done = match.group(1) in ("x", "X")
    return {"line": index, "done": is_done, "moved": is_moved, "open": not is_done and not is_moved,
            "movedTo": target.group(1) if target else None, "number": match.group(2), "title": title,
            "risk": risk.group(1).lower() if risk else "high", "closing": closing_skill(title),
            "gate": bool(GATE_CLAUSE.search(title))}


def deviation_records_move(lines, number, ticket_key):
    """True when one line of the plan's `## Plan Deviations` section names the phase and names the ticket key it moved
    to. The phase is named `Phase <id>` or `P<id>`, not followed by more of an id; an id that already starts with `P` is
    also named by itself (`P4`, `Phase P4`). The key must stand alone (`LED-16`, not `LED-160`). A line that names only
    the phase, such as a tick entry, does not count. The check only finds the words; it never judges who signed."""
    deviation_lines = [lines[index] for index in script_utils.heading_section_indexes(lines, DEVIATIONS_HEADING)]
    escaped = re.escape(number)
    bare_name = escaped if number.startswith("P") else "P" + escaped
    phase_name = re.compile(rf"(?<![A-Za-z0-9])(?:Phase\s+{escaped}|{bare_name})(?![A-Za-z0-9]|[.-][A-Za-z0-9])")
    key_name = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ticket_key)}(?![A-Za-z0-9])")
    return any(phase_name.search(line) and key_name.search(line) for line in deviation_lines)


def moved_deviation_failure(lines, entry):
    """The `moved-without-deviation` failure for a moved entry whose ticket key no Plan Deviations line records with
    the phase's name, or None. A moved entry with no key has its own failure and gives None here."""
    if not entry["moved"] or entry["movedTo"] is None:
        return None
    if deviation_records_move(lines, entry["number"], entry["movedTo"]):
        return None
    return {"line": entry["line"] + 1, "kind": "moved-without-deviation", "detail": f"Phase {entry['number']} is "
            f"marked moved, but '## {DEVIATIONS_HEADING}' has no line that names it and {entry['movedTo']}. Record "
            f"the sign-off for the move in {DEVIATIONS_HEADING} (who and when), and name Phase "
            f"{entry['number']} and {entry['movedTo']} in the same line."}


def parse_plan(lines, closing_skill=lambda title: None):
    """The plan's Phase Status entries and phase sections, with every failure sorted by line: {"entries", "sections"
    (id to the first section of that id), "failures"}. A Phase Status entry with no section is a failure unless it is
    a closing phase or a moved phase, and a section with no Phase Status entry is a failure when the plan lists any
    phase."""
    entries, failures = phase_status_entries(lines, closing_skill)
    spans, section_failures = phase_spans(lines)
    failures += section_failures

    sections = {}
    for section_id, section in spans:
        sections.setdefault(section_id, section)

    for entry in entries:
        deviation_failure = moved_deviation_failure(lines, entry)
        if deviation_failure:
            failures.append(deviation_failure)

        # A closing phase is defined by its skill, so its Phase Status line needs no section of its own. A moved phase
        # may take its section to the new ticket.
        if entry["number"] not in sections and not entry["closing"] and not entry["moved"]:
            failures.append({"line": entry["line"] + 1, "kind": "missing-section", "detail": f"Phase "
                             f"{entry['number']} is in Phase Status but the plan has no '## Phase {entry['number']}' "
                             "section."})

    status_ids = {entry["number"] for entry in entries}
    for number, section in sections.items():
        if entries and number not in status_ids:
            failures.append({"line": section["start"] + 1, "kind": "section-without-status", "detail": f"Phase "
                             f"{number} has a section but no Phase Status entry. Add `- [ ] Phase {number}: "
                             f"{section['title']}` to the Phase Status list."})

    failures.sort(key=lambda failure: failure["line"])
    return {"entries": entries, "sections": sections, "failures": failures}


def moved_phases(text, name="plan"):
    """The Phase Status entries marked `[-]` (moved to another ticket) in this plan text, in file order. A plan with no
    Phase Status gives []. A moved line with no `moved to <KEY>`, or with no Plan Deviations line that records the move,
    raises PlanFormatError that starts with `name:line:`, the same check parse_plan makes. Other lines the Phase Status
    grammar rejects are left to parse_plan, which names them."""
    lines = text.splitlines()
    entries, entry_failures = phase_status_entries(lines, lambda title: None)
    moved = [entry for entry in entries if entry["moved"]]
    failures = [failure for failure in entry_failures if failure["kind"] == "moved-without-target"]
    deviation_failures = [moved_deviation_failure(lines, entry) for entry in moved]
    failures += [failure for failure in deviation_failures if failure]
    if failures:
        first = min(failures, key=lambda failure: failure["line"])
        raise PlanFormatError(f"{name}:{first['line']}: {first['detail']}")
    return moved


def phase_at(spans, index):
    """The id of the phase section that holds this 0-based line index, or None."""
    return next((section_id for section_id, section in spans if section["start"] <= index < section["end"]), None)


def manual_heading_step(scan, line, level, name, number):
    """Moves the Manual Verification scan over one heading line: it opens, deepens or closes the section."""
    scan["last"] = None
    manual = MANUAL_HEADING.match(line)
    if manual:
        if level not in SECTION_LEVELS:
            raise PlanFormatError(f"{name}:{number}: a Manual Verification heading must be level 3 or level "
                                  f"4 (`### Manual Verification` or `#### Manual Verification`): "
                                  f"{line.strip()[:80]}")
        if not scan["in_section"] or level <= scan["section_level"]:
            scan["section_level"] = level
        scan["in_section"] = True
        scan["qualifier"] = manual.group(2)
        scan["deeper_heading"] = None
    elif scan["in_section"] and level > scan["section_level"]:
        scan["deeper_heading"] = line.strip()[:80]
    else:
        scan["in_section"] = False


def manual_line_step(scan, line, is_fenced, name, position):
    """Moves the Manual Verification scan over one non-heading line inside the section. `position` is the 1-based
    line number and the phase id of the line."""
    number, phase = position
    if is_fenced:
        raise PlanFormatError(f"{name}:{number}: a fenced block inside Manual Verification; write each step "
                              f"as a list item: {line.strip()[:80]}")
    if not line.strip():
        return

    if line[0] in " \t":
        if scan["last"] is None:
            raise PlanFormatError(f"{name}:{number}: indented line with no list item above it in Manual "
                                  f"Verification: {line.strip()[:80]}")
        scan["last"]["text"] += " " + line.strip()
        return

    entry = LIST_ENTRY.match(line)
    if entry and scan["deeper_heading"]:
        raise PlanFormatError(
            f"{name}:{number}: a list item under the sub-heading `{scan['deeper_heading']}` inside Manual "
            f"Verification; if that heading starts a new section, give it the Manual Verification "
            f"heading's level or a higher one, otherwise move the item above it: "
            f"{line.strip()[:80]}"
        )
    if entry and (entry.group(1) is not None or not NOT_APPLICABLE.match(line)):
        scan["last"] = {"phase": phase, "text": entry.group(2).strip(),
                        "checked": (entry.group(1) or "").lower() == "x", "line": number,
                        "heading": scan["qualifier"]}
        scan["items"].append(scan["last"])
        return

    scan["last"] = None
    if line.startswith(FOREIGN_START):
        raise PlanFormatError(f"{name}:{number}: line shape not allowed in Manual Verification (table, quote or "
                              f"HTML): {line.strip()[:80]}")


def manual_verification(text, name="plan"):
    """Every item of every Manual Verification section, in file order.

    Each item is {"phase": the id of the `## Phase <id>` heading above it or None, "text": the item with its indented
    lines folded in, "checked": True for `[x]`, "line": the 1-based line of the item, "heading": the qualifier text
    after the section's heading words, "humanOnly": True only when the heading qualifier or the item text says
    "human-only" (any case); an unmarked item is run by an agent, as the plan template tells the writer to mark the
    items only a person can judge, "verified": True for a checked item, or an item that is not human-only and says
    "agent-verified" (any case); any other agent-run item has not been run yet}. Items are folded in whole: "text"
    includes the wrapped lines, so the mark counts wherever it sits in the item. Raises PlanFormatError for a line the
    grammar does not parse."""
    lines = text.splitlines()
    fenced = script_utils.fenced_line_indexes(lines)
    spans, _ = phase_spans(lines)
    scan = {"items": [], "in_section": False, "section_level": 0, "deeper_heading": None, "qualifier": "",
            "last": None}

    for index, line in enumerate(lines):
        number = index + 1
        is_fenced = index in fenced
        heading = None if is_fenced else script_utils.MARKDOWN_HEADING.match(line)

        if not is_fenced and line.strip() == "---":
            scan["in_section"] = False
            scan["last"] = None
        if heading:
            heading_marks = heading.group(1)
            manual_heading_step(scan, line, len(heading_marks), name, number)
            continue
        if scan["in_section"]:
            phase_id = phase_at(spans, index)
            manual_line_step(scan, line, is_fenced, name, (number, phase_id))

    items = scan["items"]
    for item in items:
        item["humanOnly"] = HUMAN_ONLY_MARK in item["heading"].lower() or HUMAN_ONLY_MARK in item["text"].lower()
        item["verified"] = item["checked"] or (not item["humanOnly"] and AGENT_VERIFIED_MARK in item["text"].lower())
    return items


AUTOMATED_HEADING = "#### Automated Verification"
# A level 2 or 3 heading that opens an acceptance-criteria section, in any wording that starts with "Acceptance".
ACCEPTANCE_HEADING = re.compile(r"^#{2,3}\s+acceptance\b", re.IGNORECASE)
AUTOMATED_ITEM = re.compile(r"^- \[[ x]\]")
# A top-level list item of any marker: "- x", "* x", "+ x", "1. x", "1) x".
TOP_LEVEL_LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s")
AUTOMATED_ITEM_BOX = re.compile(r"^- \[[ x]\]\s*")
SPEC_FILE_NAME = "spec.md"
PLAN_FILES_GLOB = f"docs/plans/*/{SPEC_FILE_NAME}"
GATE_ENV_HINT = "(Put these variables before every test, check or build command you run.)"

# An Automated Verification item that says there is nothing to run: "- [ ] N/A — docs only", "- [ ] none".
# A bold label may come first when the word after it is N/A: "- [ ] **Test-verified**: N/A on the machines."
NO_AUTOMATED_CHECK = re.compile(r"^- \[[ x]\]\s*(?:[*_`]*\s*(?:n/a|none)\b|\*\*[^*]+\*\*:?\s*n/a\b)", re.IGNORECASE)

# An Automated Verification item that the code step never runs because the plan says another place does:
# "- [ ] **CI-verified**: the pipeline runs it", "- [ ] Human-only: look at the page", "- [ ] **Agent-run**: time the
# import on the real data" (the session or the branch check runs it and records its output). A bold label may come
# first.
DEFERRED_VERIFICATION = re.compile(
    r"^- \[[ x]\]\s*(?:\*\*[^*]+\*\*:?\s*)?[*_`]*\s*(?P<tag>ci-verified|human-only|agent-run)\b", re.IGNORECASE)
AGENT_RUN_TAG = "agent-run"
DEFERRED_TAG_NAMES = {"ci-verified": "CI-verified", "human-only": "human-only", AGENT_RUN_TAG: AGENT_RUN_TAG}


def automated_verification_rows(lines, name="plan", first_line=1, strict=False):
    """(index, line) for each item under a `#### Automated Verification` heading, in file order. A top-level list item
    that is not a checkbox (`- \\`make test\\``, `1. N/A — docs only`) is read as an open box: its line comes back as
    `- [ ] <text>`. See verification_list_items for where the list ends and what `strict` raises."""
    verification_items = []
    for index, line in verification_list_items(lines, name, first_line, strict):
        if not AUTOMATED_ITEM.match(line):
            line = TOP_LEVEL_LIST_ITEM.sub("- [ ] ", line, count=1)
        verification_items.append((index, line))
    return verification_items


def plain_verification_item_warnings(lines, name="plan", first_line=1):
    """One `name:line: warning:` row for each top-level list item under Automated Verification that is not a checkbox,
    which automated_verification_rows reads as an open box."""
    return [
        f"{name}:{first_line + index}: warning: list item `{line.strip()[:80]}` under `{AUTOMATED_HEADING}` is not a "
        f"checkbox; it is read as an open `- [ ]` check. Write it as `- [ ] <check>` (or `- [ ] N/A — <reason>`), or "
        f"move it out of the section"
        for index, line in verification_list_items(lines, name, first_line)
        if not AUTOMATED_ITEM.match(line)
    ]


def _is_automated_heading(line, location, strict):
    """True for the Automated Verification heading. With `strict`, any other `#### ` heading that names automated
    verification in other words raises PlanFormatError."""
    if line.startswith(AUTOMATED_HEADING):
        return True
    if strict:
        _refuse_misworded_heading(line, location)
    return False


def _refuse_misworded_heading(line, location):
    """Raise PlanFormatError when a `#### ` heading names automated verification in words other than the
    Automated Verification heading."""
    lowered = line.lower()
    misworded = "automated" in lowered and "verif" in lowered and not MANUAL_HEADING.match(line)
    if not misworded:
        return
    raise PlanFormatError(
        f"{location}: heading `{line.strip()}` is not a verification heading; "
        f"rename it to `{AUTOMATED_HEADING}` for commands, or `#### Manual Verification:` for human "
        f"checks, or its items are not read"
    )


def verification_list_items(lines, name="plan", first_line=1, strict=False):
    """(index, line) for each top-level list item under a `#### Automated Verification` heading, checkbox or not, in
    file order. The list ends at the next `#### ` heading, a heading of level 1 to 3, or a `---` rule. A `#### `
    heading that names automated verification in other words raises PlanFormatError when `strict` is set
    (`name:line:`; `first_line` is the file line of lines[0]), because its items would otherwise be read as absent. A
    Manual Verification heading is never misworded."""
    verification_items = []
    inside = False
    for index, line in enumerate(lines):
        if line.startswith("#### "):
            inside = _is_automated_heading(line, f"{name}:{first_line + index}", strict)
            continue
        if re.match(r"#{1,3} ", line) or line.strip() == "---":
            inside = False
        if inside and TOP_LEVEL_LIST_ITEM.match(line):
            verification_items.append((index, line))
    return verification_items


# A `git diff` span that ends or starts at a branch name that moves: `main...HEAD`, `origin/master..HEAD`. Once the
# branch merges, that span is empty, so a box that diffs it passes after merge with nothing read.
MOVING_BASE_DIFF = re.compile(
    r"git\s+(?:-\S+\s+)*diff\b[^`\n]*?(?<![\w./-])(?:origin/|upstream/)?(?:main|master|develop|trunk)\.\.\.?[\w./^~-]+")
MOVING_BASE_DIFF_FIX = (
    "it diffs a moving branch name, which is empty once the branch merges. Diff two recorded commit ids "
    "(`<base-sha>..<head-sha>`) or the merge's first parent (`<merge-sha>^1..<merge-sha>`), and make the box fail "
    "on an empty diff: `test -n \"$(git diff --name-only <base-sha>..<head-sha>)\"`")


def moving_base_diff(line):
    """True for an Automated Verification item whose command diffs a span that starts at a branch name that moves."""
    return bool(MOVING_BASE_DIFF.search(line))


def automated_item_text(line):
    """The words of an Automated Verification item, without the `- [ ]` box."""
    return AUTOMATED_ITEM_BOX.sub("", line.strip())


def deferred_verification_tag(line):
    """"CI-verified", "human-only" or "agent-run" for an Automated Verification item tagged that way, else None."""
    tag_match = DEFERRED_VERIFICATION.match(line)
    return DEFERRED_TAG_NAMES[tag_match.group("tag").lower()] if tag_match else None


def runs_no_command(line):
    """True for an Automated Verification item that gets no command run: it says N/A or none, or it is left to CI or
    a person, or it is tagged Agent-run (the session or the branch check runs it, never the plan check)."""
    return bool(NO_AUTOMATED_CHECK.match(line) or deferred_verification_tag(line))


def gate_env(plan_text):
    """The `NAME=value` words that the plan's Automated Verification commands start with, one per name, in file order.
    An item that says N/A or is left to CI, a person, or an agent (Agent-run) is not a command that gets run, so it
    gives none."""
    verification_items = automated_verification_rows(plan_text.splitlines())
    runnable_items = [line for _, line in verification_items if not runs_no_command(line)]
    spans = []
    for line in runnable_items:
        spans += script_utils.backticked_spans(line)
    return script_utils.leading_env_assignments(spans)


def gate_env_text(gate_env_assignments):
    """The two lines that tell an agent which variables to put before its gate commands, or "" when there are none."""
    if not gate_env_assignments:
        return ""
    return f"gate-env: {' '.join(gate_env_assignments)}\n{GATE_ENV_HINT}"


def gate_env_words_in(prompt_text):
    """The `NAME=value` words of the prompt's `gate-env:` line, as written, or []."""
    match = re.search(r"^gate-env:[ \t]*(.+)$", prompt_text, re.M)
    if not match:
        return []
    return [word.group(0) for word in script_utils.ENV_ASSIGNMENT.finditer(match.group(1))]


def plan_gate_env(root, plan_rel):
    """What `gate_env` reads from the plans under docs/plans/*/spec.md. A run whose own plan `plan_rel` (a path
    under root) is readable gets only that plan's names. A run with no readable plan takes a name the other plans set
    when they all give it the same value; a name they give different values is left out, since no plan says which
    one this run needs."""
    if plan_rel:
        own_assignments = own_plan_gate_env(root, plan_rel)
        if own_assignments is not None:
            return own_assignments

    return agreed_gate_env(root, plan_rel)


def own_plan_gate_env(root, plan_rel):
    """The run's own plan's assignments, the last one per name winning, or None when the plan cannot be read."""
    try:
        own_text = (root / plan_rel).read_text()
    except OSError:
        return None

    return script_utils.last_per_name(gate_env(own_text))


def agreed_gate_env(root, plan_rel):
    """The assignments of every plan but `plan_rel` whose name all those plans give the same value."""
    seen = {}
    for plan_path in sorted(root.glob(PLAN_FILES_GLOB)):
        if plan_rel and plan_path.resolve() == (root / plan_rel).resolve():
            continue
        try:
            assignments = gate_env(plan_path.read_text())
        except OSError:
            continue
        for assignment in assignments:
            seen.setdefault(assignment.split("=", 1)[0], set()).add(assignment)

    return [next(iter(variants)) for variants in seen.values() if len(variants) == 1]


CLOSING_TITLE_END = r"\b(?!\s*\w)"
CLOSING_PHASES = [
    (re.compile(r"^Refactor pass" + CLOSING_TITLE_END, re.I), "/refactor +deep"),
    (re.compile(r"^Test audit" + CLOSING_TITLE_END, re.I), "/test-audit"),
    (re.compile(r"^Verify pass" + CLOSING_TITLE_END, re.I), "/verify-branch"),
    (re.compile(r"^Recap" + CLOSING_TITLE_END, re.I), "/branch-recap"),
    (re.compile(r"^Close pass" + CLOSING_TITLE_END, re.I), "/close-branch"),
]


def closing_skill(title):
    """The skill a closing phase's title names (`Verify pass` names /verify-branch), or None for any other title."""
    return next((skill for pattern, skill in CLOSING_PHASES if pattern.search(title)), None)


def cited_phases(plan_lines, phase_id, phase_text):
    """(id, start, end) of each other phase that the phase text reuses with 'same as Phase N', directly or through
    another cited phase's own citation, start 1-based."""
    cited = []
    seen = {phase_id}
    pending = [phase_text]
    while pending:
        for cited_id, section in _unseen_cited_sections(plan_lines, pending.pop(), seen):
            cited.append((cited_id, section["start"] + 1, section["end"]))
            pending.append("\n".join(plan_lines[section["start"]:section["end"]]))
    return cited


def _unseen_cited_sections(plan_lines, text, seen):
    """(id, section) for each phase the text cites that has a section and is not in `seen`, which gains its id."""
    sections = []
    for match in SAME_AS_PHASE.finditer(text):
        cited_id = match.group(1)
        section = phase_section(plan_lines, cited_id)
        if section is None or cited_id in seen:
            continue
        seen.add(cited_id)
        sections.append((cited_id, section))
    return sections


def parse_plan_with_closing_phases(plan_lines):
    """parse_plan with the closing phases recognised by their titles."""
    return parse_plan(plan_lines, closing_skill)


def phase_text(plan_lines, number):
    """The text of the phase's section, or None when the plan has no section for it."""
    section = phase_section(plan_lines, number)
    if section is None:
        return None
    return "\n".join(plan_lines[section["start"]:section["end"]])


def append_deviation(plan_path, entry):
    """Add the entry lines at the end of the plan's `## Plan Deviations` section, creating the section before
    `## References` (or at the end) when the plan has none."""
    lines = plan_path.read_text().split("\n")
    sections = script_utils.top_level_sections(lines)
    existing = next((i for i in sections if lines[i].strip() == "## Plan Deviations"), None)
    if existing is not None:
        end = next((i for i in sections if i > existing), len(lines))
        lines[end:end] = [*entry, ""]
    else:
        references = next((i for i in sections if lines[i].strip() == "## References"), len(lines))
        lines[references:references] = ["## Plan Deviations", "", *entry, ""]
    plan_path.write_text("\n".join(lines))


def changes_acceptance_criteria(impact):
    """False only when each PLAN-IMPACT in impact says `acceptance_criteria: none`. A PLAN-IMPACT with no such line
    counts as an AC change, so the user is asked."""
    answers = [match.group(1).strip(" \t.`*_").lower() for match in AC_CHANGE_LINE.finditer(impact)]
    openings = PLAN_IMPACT_OPENING.findall(impact)
    impacts = max(1, len(openings))
    return len(answers) < impacts or any(answer != "none" for answer in answers)


def plan_impact_cause(block, missing=PLAN_CAUSE):
    """The block's `cause:` value, lowercased; `missing` when the block has no cause key. A value outside
    PLAN_IMPACT_CAUSES comes back lowercased, for the caller to refuse."""
    match = PLAN_IMPACT_CAUSE.search(block)
    if not match:
        return missing
    return match.group(1).strip().lower()


def block_must_name_cause(block):
    """True for a readable PLAN-IMPACT block (header line, then its lines). A report that only says `PLAN-IMPACT: yes`
    has no block to read, so it has no cause to name."""
    return block.startswith(PLAN_IMPACT_BLOCK_HEADER)


def stopping_plan_impact_cause(blocks, cause_required=False):
    """The one cause for several PLAN-IMPACT blocks, each read on its own so no block borrows another's line: the
    first block whose cause is not `plan` (`toolkit`, a missing `cause:` line, or a cause that does not parse), else
    `plan`. The cause comes back lowercased (cause_stop words it). With
    `cause_required` a readable block with no cause key carries NO_CAUSE_LINE, which survives a packet field that
    reads an empty cause as `plan`."""
    for block in blocks:
        required = cause_required and block_must_name_cause(block)
        missing_cause = NO_CAUSE_LINE if required else PLAN_CAUSE
        cause = plan_impact_cause(block, missing=missing_cause)
        if cause_stop(cause):
            return cause or NO_CAUSE_LINE
    return PLAN_CAUSE


def cause_stop(cause):
    """The words for a cause that is not `plan`: `toolkit`, a missing `cause:` line, or a cause that does not parse.
    None for `plan`, which goes on to the plan rewrite."""
    if cause == TOOLKIT_CAUSE:
        return "reported a toolkit gate or script fault with nothing wrong in the plan. Fix the toolkit, not the plan"
    if not cause or cause == NO_CAUSE_LINE:
        return f"wrote a PLAN-IMPACT with no `cause:` line: the cause is {' or '.join(PLAN_IMPACT_CAUSES)}"
    if cause not in PLAN_IMPACT_CAUSES:
        return (f"wrote a PLAN-IMPACT `cause: {cause}` that does not parse: the cause is "
                f"{' or '.join(PLAN_IMPACT_CAUSES)}")
    return None


def below_criteria_summary(impact):
    """What the plan assumed and what the code does, on one line."""
    without_marks = PLAN_IMPACT_HEADER_WORD.sub(" ", impact)
    disagreement = AC_CHANGE_CLAUSE.sub(" ", without_marks)
    return script_utils.one_line(disagreement, limit=400).strip(" ;,—-")


def below_criteria_ruling(impact):
    """The ruling for a plan change that changes no acceptance criterion, with its summary."""
    return f"{BELOW_CRITERIA_RULING} {below_criteria_summary(impact)}"


USER_RULING = "user"
SESSION_RULING = "session"


def ruling_owner(repo_dir, by):
    """Who a plan-impact ruling is signed by: the git user name for `--by user`, the session otherwise."""
    if by != USER_RULING:
        return SESSION_RULING_OWNER
    return script_utils.git_output(repo_dir, "config", "user.name") or "the user"


PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
PLAN_CHECK_OWNER_COMMAND = "python3 ~/.claude/scripts/code/plan_check.py owner <plan>"
PLAN_OWNER_RULE_CONDITION = "the ticket's own words, or with no ticket the user's own request, stay met"
DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling changes an acceptance criterion only when "
                  f"`{PLAN_CHECK_OWNER_COMMAND}` names `session` or `plan`, and for `plan` only while "
                  f"{PLAN_OWNER_RULE_CONDITION}.")
DECIDE_USAGE_STEM = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'


def is_ruling_by(by):
    """True when a `--by` value names who ruled: the user or the session."""
    return by in (USER_RULING, SESSION_RULING)


def ruled_at_now():
    """The current time in the "YYYY-MM-DD HH:MM" form `ruling_deviation` takes."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def ruling_deviation(phase, decision, owner, ruled_at, ruling_words, disagreement):
    """The `## Plan Deviations` entry lines for one plan-impact ruling. `ruled_at` is "YYYY-MM-DD HH:MM"; a phase of
    None leaves the phase out of the entry's first line."""
    ruled_on = ruled_at.split()[0]
    dated = f"- {ruled_on} (Phase {phase})" if phase is not None else f"- {ruled_on}"
    ruling_line = " ".join(ruling_words.split())
    entry = [f"{dated}: {decision}. Ruled by {owner} at {ruled_at}.", "", f"{DEVIATION_RULING_PREFIX}{ruling_line}",
             "", "  The disagreement:"]
    entry += ["  " + line for line in disagreement.splitlines()]
    return entry


CARRIED_FINDINGS_KEY = "carried-findings:"
RESOLVED_BLOCK_PATTERN = r"^[ \t>*`-]*RESOLVED:"
RESOLVED_BLOCK_LINE = re.compile(RESOLVED_BLOCK_PATTERN)
# The PLAN-IMPACT label inside a line of the block a RESOLVED: line settles: bold or backticked or plain, after an
# optional location prefix such as `path:14 [docs] — `. The text after the label is the impact text.
RESOLVED_IMPACT_HEADER = re.compile(r"PLAN-IMPACT[*`_]*:[*`_]*")
RESOLVED_RULING_LINE = re.compile(
    rf"^[ \t>*`-]*(?i:plan_impact):[ \t]*RESOLVED\b|{RESOLVED_BLOCK_PATTERN}")


def ruled_impact_text(lines, index, indent):
    """The PLAN-IMPACT text under the RESOLVED: line at `index`, or None when the block holds no PLAN-IMPACT label.
    The block ends at a line indented less than the RESOLVED: line or at a carried-findings: line."""
    block = []
    for later in lines[index + 1:]:
        if not later.strip():
            continue
        if source_text.indent_of(later) < indent or later.strip().startswith(CARRIED_FINDINGS_KEY):
            break
        block.append(later.strip())
    for position, entry in enumerate(block):
        header = RESOLVED_IMPACT_HEADER.search(entry)
        if header:
            header_rest = entry[header.end():].strip()
            return " ".join(filter(None, [header_rest, *block[position + 1:]]))
    return None


def _ruled_impact_texts(lines, index, indent):
    """The PLAN-IMPACT text under the RESOLVED: line as a one-item list, or [] when the block holds none."""
    impact_text = ruled_impact_text(lines, index, indent)
    if impact_text is None:
        return []
    return [impact_text]


def resolved_plan_texts(handoff):
    """The texts a handoff with a ruling names as settled: the ruling line (the one-line `plan_impact: RESOLVED` form
    or the `RESOLVED:` line of the `plan_impact: |` block), the PLAN-IMPACT block that follows the `RESOLVED:` line,
    and each carried finding. Empty when the handoff holds no ruling."""
    lines = handoff.splitlines()
    texts = []
    ruled = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = source_text.indent_of(line)
        if RESOLVED_RULING_LINE.match(line):
            ruled = True
            texts.append(stripped)
        if RESOLVED_BLOCK_LINE.match(line):
            texts += _ruled_impact_texts(lines, index, indent)
        elif stripped.startswith(CARRIED_FINDINGS_KEY):
            texts += _carried_finding_texts(lines, index, indent)
    return texts if ruled else []


def _carried_finding_texts(lines, index, indent):
    """The `- ` entries under the carried-findings: line at `index`, without the dash. They end at a line indented no
    deeper than that line."""
    following = []
    for later in lines[index + 1:]:
        if later.strip() and source_text.indent_of(later) <= indent:
            break
        following.append(later.strip())
    return [entry[2:] for entry in following if entry.startswith("- ")]


def plan_failure_rows(plan, plan_name):
    return [f"{plan_name}:{f['line']}: {f['kind']}: {f['detail']}" for f in plan["failures"]]


def manual_format_message(error, resume_line=""):
    message = ("The plan's Manual Verification section does not parse. Do not mark the phase done. Report to the "
               f"user and stop:\n{error}")
    return message + ("\n" + resume_line if resume_line else "")


def manual_format_failure(plan_lines, plan_name, resume_line=""):
    """The stop message for a Manual Verification section the grammar does not parse, or None when all parse."""
    try:
        manual_verification("\n".join(plan_lines), plan_name)
    except PlanFormatError as error:
        return manual_format_message(error, resume_line)
    return None


# Acceptance-criteria cross-references. spec.md is written before acceptance-criteria.md, so a bare `AC<n>` in the spec
# can only be the ticket's numbering, while the criteria file numbers its own. A bare `AC<n>` must therefore name
# criterion n of the criteria file (the spec line shares at least two content words with it); a reference to the
# ticket's number is written "ticket AC<n>". `AC` is upper case and stands alone: `ac3-evidence.md` and
# `test_ac1_x` are names, not references.
CRITERION_LINE = re.compile(r"^\s*[-*]\s+\**(AC\d+)\**\s*[:.—–-]*\s*(.*)$")
AC_REFERENCE = re.compile(r"(?<![A-Za-z0-9_])(?P<ticket>(?i:ticket)\s+)?AC(?P<number>\d+)(?![A-Za-z0-9_])")
CONTENT_WORD = re.compile(r"[a-z]{4,}")
AC_STOP_WORDS = frozenset({"that", "this", "with", "from", "when", "then", "than", "into", "must", "shall", "will",
                           "have", "does", "each", "every", "criterion", "criteria", "ticket", "spec", "plan"})
MIN_SHARED_WORDS = 2
CRITERIA_FILE_NAME = "acceptance-criteria.md"
PLAN_ONLY_PLAN_NAME = "plan.md"


def criteria_by_id(criteria_text, name=CRITERIA_FILE_NAME):
    """{"AC<n>": criterion text} for each `- **AC<n>** — text` line of the criteria file. A duplicate id raises
    PlanFormatError (`name:line:`)."""
    criteria = {}
    for number, line in enumerate(criteria_text.splitlines(), start=1):
        match = CRITERION_LINE.match(line)
        if not match:
            continue
        criterion_id = match.group(1).upper()
        if criterion_id in criteria:
            raise PlanFormatError(f"{name}:{number}: {criterion_id} is defined twice; give each criterion its own id")
        criteria[criterion_id] = match.group(2)
    return criteria


def content_words(text):
    words = CONTENT_WORD.findall(text.lower())
    return set(words) - AC_STOP_WORDS


def missing_criteria_failure(spec_path):
    """The one row for a spec with an Acceptance Criteria section whose acceptance-criteria.md beside it is missing
    or empty, else None. Run by `plan check --final` and by `/code` start; plain `plan check` skips it because the
    criteria file is written after the spec."""
    has_criteria_section = any(ACCEPTANCE_HEADING.match(line) for line in spec_path.read_text().splitlines())
    if not has_criteria_section:
        return None

    criteria_path = spec_path.with_name(CRITERIA_FILE_NAME)
    if criteria_path.is_file() and criteria_path.read_text().strip():
        return None
    return (f"{criteria_path}: missing or empty, and the spec has an Acceptance Criteria section. The spec-criteria "
            "step never ran: dispatch spec-criteria (eng-spec Phase 6, step 17), never write the file yourself.")


def spec_ac_failures(spec_path):
    """The finalization rows for a file named spec.md: the ac_reference_failures rows read against the
    acceptance-criteria.md beside it (a missing file is None) and the ac_drift_failures rows against the ticket beside
    it (checked only when both the ticket and the criteria file exist). Any other file name gives []. A criteria file
    with a repeated id gives its one error row. A ticket with no criteria heading is not checked for drift."""
    if spec_path.name != SPEC_FILE_NAME:
        return []
    spec_text = spec_path.read_text()
    failures = []
    criteria_path = spec_path.with_name(CRITERIA_FILE_NAME)
    criteria_text = criteria_path.read_text() if criteria_path.is_file() else None
    try:
        ticket_path = ticket_beside(spec_path)
        failures += ac_reference_failures(spec_text, criteria_text, str(spec_path), str(criteria_path))
        if criteria_text is not None and ticket_path is not None:
            owner = criteria_owner(ticket_path)["owner"]
            failures += ac_drift_failures(ticket_path.read_text(), criteria_text, spec_text, str(ticket_path),
                                          str(criteria_path), owner)
    except PlanFormatError as error:
        failures.append(str(error))
    return failures


def ac_reference_failures(spec_text, criteria_text, spec_name=SPEC_FILE_NAME, criteria_name=CRITERIA_FILE_NAME):
    """One `name:line: message` string for each bare `AC<n>` in the spec that does not name criterion n of the
    criteria file. `criteria_text` None means the criteria file does not exist, so every bare reference fails. A
    reference written `ticket AC<n>` is never checked. Fenced blocks are skipped. The line holding the reference, and
    the line after it, must share at least MIN_SHARED_WORDS content words with the criterion."""
    criteria = criteria_by_id(criteria_text, criteria_name) if criteria_text is not None else {}
    lines = spec_text.splitlines()
    fenced = script_utils.fenced_line_indexes(lines)
    failures = []
    for index, criterion_id in _bare_references(lines, fenced):
        window = " ".join(lines[index:index + 2])
        nearby = content_words(window)
        where = f"{spec_name}:{index + 1}:"
        failure = _ac_reference_failure(criterion_id, where, criteria, criteria_name, nearby)
        if failure:
            failures.append(failure)
    return failures


def _bare_references(lines, fenced):
    """(line index, "AC<n>") for each bare `AC<n>` outside fenced blocks, in file order; `ticket AC<n>` is left out."""
    references = []
    for index, line in enumerate(lines):
        if index in fenced:
            continue
        references += [(index, criterion_id) for criterion_id in _bare_ids_in(line)]
    return references


def _bare_ids_in(line):
    """The "AC<n>" of each bare reference on the line; a `ticket AC<n>` is left out."""
    ids = []
    for reference in AC_REFERENCE.finditer(line):
        if not reference.group("ticket"):
            ids.append(f"AC{reference.group('number')}")
    return ids


def _ac_reference_failure(criterion_id, where, criteria, criteria_name, nearby):
    """The failure row for one bare `AC<n>` reference, or None when it names its criterion."""
    if criterion_id not in criteria:
        return (f"{where} {criterion_id} is not an id in {criteria_name}; write "
                f"`ticket {criterion_id}` for the ticket's number, or cite the criteria file's id")
    criterion_words = content_words(criteria[criterion_id])
    if len(nearby & criterion_words) >= MIN_SHARED_WORDS:
        return None
    return (f"{where} {criterion_id} shares no wording with {criterion_id} in {criteria_name} "
            f"({criteria[criterion_id][:60]!r}); it may be the ticket's number. Write "
            f"`ticket {criterion_id}`, or name the criterion's behavior beside it")


# The ticket's acceptance criteria. verify-prep, verify-log and the plan check all read them through ticket_criteria.
AC_HEADING = re.compile(r"^(#{2,3})\s+(?:acceptance(?:\s+criteria)?|requirements)\s*:?\s*$", re.I)
AC_HEADING_LOOSE = re.compile(r"^(#{2,3})\s+(?:acceptance|requirements)\b", re.I)
LISTITEM = re.compile(r"^(\s*)(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$")


# The plan-wide test rules. The review loop hands this section to the test reviewer beside the phase.
TEST_STRATEGY_HEADING = re.compile(r"^#{2,3}\s+test(?:ing)?\s+strategy\b", re.I)


def heading_level(line):
    match = re.match(r"^(#+)\s", line)
    return len(match.group(1)) if match else 0


def section_body(lines, start_index):
    """Lines under lines[start_index] up to a heading of the same or higher level, or a `---` rule."""
    level = heading_level(lines[start_index])
    body = []
    for line in lines[start_index + 1:]:
        if line.strip() == "---":
            break
        next_level = heading_level(line)
        if next_level and next_level <= level:
            break
        body.append(line)
    return body


def test_strategy_range(plan_lines):
    """(start, end) of the test strategy section as 0-based start and exclusive end indexes, heading included,
    or None when the plan has none. A heading inside a fenced block, or before the first phase, does not count."""
    fenced = script_utils.fenced_line_indexes(plan_lines)
    spans, _ = phase_spans(plan_lines)
    first_phase = min((span["start"] for _, span in spans), default=0)
    start = next(
        (
            index for index, line in enumerate(plan_lines)
            if index >= first_phase and index not in fenced and TEST_STRATEGY_HEADING.match(line)
        ),
        None,
    )
    if start is None:
        return None

    return start, start + 1 + len(section_body(plan_lines, start))


def test_strategy_section(plan_lines):
    """The plan's test strategy section, heading included, or "" when the plan has none."""
    section_range = test_strategy_range(plan_lines)
    if section_range is None:
        return ""

    start, end = section_range
    return "\n".join(plan_lines[start:end]).strip()


def top_level_items(body, name="section", first_line=1):
    """Top-level list items of a section; wrapped and nested lines are folded into the item above.

    A line at column 0 that is not a list item but holds a word is prose the parse would drop: it raises
    PlanFormatError with `name:line`. `first_line` is the file line number of body[0]."""
    items = []
    for offset, line in enumerate(body):
        match = LISTITEM.match(line)
        is_prose = (not match and line.strip() and not line.startswith((" ", "\t")) and re.search(r"\w", line))
        if is_prose:
            raise PlanFormatError(f"{name}:{first_line + offset}: prose in the criteria section is not a list item, "
                                  f"so it would be skipped: {line.strip()[:80]}")
        _fold_item_line(items, match, line)
    return items


def _fold_item_line(items, match, line):
    """Add the line to `items`: a new item for a top-level list line, else folded into the item above."""
    if match and len(match.group(1)) < 2:
        items.append(match.group(2).strip())
        return
    if match and items:
        items[-1] += " " + match.group(2).strip()
        return
    if line.strip() and line.startswith((" ", "\t")) and items:
        items[-1] += " " + line.strip()


def ticket_criteria(ticket_text, name="ticket"):
    """Criteria from a ticket (or legacy flat plan), numbered in order and labelled by source
    (`Ticket #2`): the ticket's own numbering, never an id from the criteria file. Raises PlanFormatError when none
    are found or when a heading starts like a criteria heading but is not one."""
    lines = ticket_text.splitlines()
    for number, line in enumerate(lines, 1):
        if AC_HEADING_LOOSE.match(line) and not AC_HEADING.match(line):
            raise PlanFormatError(
                f"{name}:{number}: heading `{line.strip()}` is not a recognized criteria heading "
                "(`Acceptance`, `Acceptance` + `criteria`, `Requirements`); rename it or what it holds is not read"
            )
    candidates = [i for i, line in enumerate(lines) if AC_HEADING.match(line)]
    if not candidates:
        raise NoCriteriaHeadingError(f"{name}: no `## Acceptance*` or `## Requirements*` heading in the ticket; "
                                "refusing to treat zero criteria as a pass")
    candidates.sort(key=lambda i: (heading_level(lines[i]), i))
    for index in candidates:
        items = top_level_items(section_body(lines, index), name, index + 2)
        if items:
            return [{"number": n, "label": f"Ticket #{n}", "text": text} for n, text in enumerate(items, 1)]
    raise PlanFormatError(
        f"{name}: heading `{lines[candidates[0]].strip()}` has no list items; refusing to treat zero criteria as a pass"
    )


# The ticket's comments. A comment can add or change a criterion, so verify-prep lists each one as a label.
COMMENTS_HEADING = re.compile(r"^(#{2,3})\s+comments\s*:?\s*$", re.I)
COMMENTS_FIELD = re.compile(r"^[*_]*comments:?[*_]*:?\s*(.*)$", re.I)
COMMENT_LABEL = "Comment #"
NO_COMMENTS = re.compile(r"^[*_]*(?:none|no comments)\.?[*_]*$", re.I)


def comment_entries(texts):
    return [{"number": n, "label": f"{COMMENT_LABEL}{n}", "text": text} for n, text in enumerate(texts, 1)]


def field_comment_texts(lines):
    """The values of `Comments: <text>` field lines, leaving out `none`."""
    texts = []
    for line in lines:
        field = COMMENTS_FIELD.match(line.strip())
        if not field:
            continue
        value = field.group(1).strip()
        if value and not NO_COMMENTS.match(value):
            texts.append(value)
    return texts


def ticket_comments(ticket_text, name="ticket"):
    """Comments from a persisted ticket, numbered in order and labelled `Comment #n`. The ticket holds them under a
    `## Comments` heading, one `###` heading per comment (author and date) with its body below; a section with no
    sub-heading is one comment. `none` there, or a `Comments: none` field line, means no comments. Text before the
    first sub-heading raises PlanFormatError: it belongs to no comment."""
    lines = ticket_text.splitlines()
    start = next((index for index, line in enumerate(lines) if COMMENTS_HEADING.match(line)), None)
    if start is None:
        return comment_entries(field_comment_texts(lines))

    body = section_body(lines, start)
    words = [line.strip() for line in body if line.strip()]
    if not words or (len(words) == 1 and NO_COMMENTS.match(words[0])):
        return []

    sub_level = heading_level(lines[start]) + 1
    has_sub_headings = any(heading_level(line) == sub_level for line in body)
    if not has_sub_headings:
        return comment_entries([" ".join(words)])

    comments = []
    for offset, line in enumerate(body):
        if heading_level(line) == sub_level:
            comments.append([line.lstrip("#").strip()])
            continue
        if not line.strip():
            continue
        if not comments:
            raise PlanFormatError(f"{name}:{start + 2 + offset}: text under `{lines[start].strip()}` before the "
                                  f"first `{'#' * sub_level}` comment heading belongs to no comment: "
                                  f"{line.strip()[:80]}")
        comments[-1].append(line.strip())
    return comment_entries([" ".join(parts) for parts in comments])


# Who owns a ticket's criteria, and so who may cut or reword one. A ticket copied from a queue item names the item in a
# `Source:` line; the item's `generated.by` says whether a person or a session wrote the criteria.
CRITERIA_OWNER_USER = "user"
CRITERIA_OWNER_PLAN = "plan"
CRITERIA_OWNER_SESSION = "session"
CRITERIA_OWNER_RULES = {
    CRITERIA_OWNER_USER: "only the user's recorded sign-off (who and when) cuts, narrows or rewords a criterion",
    CRITERIA_OWNER_PLAN: "the plan author wrote the criteria (the ticket has no criteria heading, or there is no "
                         f"ticket): the session may cut or reword one while {PLAN_OWNER_RULE_CONDITION}, "
                         "records the ruling in the plan's decision log "
                         "(`03-decisions.md` or `## Plan Deviations`), and asks the user otherwise",
    CRITERIA_OWNER_SESSION: "a session wrote this ticket's criteria: the session may rule on a change to one and "
                            "records the ruling; no user sign-off is needed",
}
QUEUE_SOURCE_PREFIX = "~/agent-evals/queue/"
QUEUE_SOURCE_FORM = re.compile(r"^~/agent-evals/queue/[a-z0-9-]+\.md(?: .*)?$")
SOURCE_LINE = re.compile(r"^(?:-\s+)?source:\s*(.*)$", re.I)
GENERATED_FORM = 'generated: {"by": "<author>", ...}'
HUMAN_AUTHOR_PREFIX = "human:"


def queue_source_line(ticket_lines):
    """(line number, value) of the ticket's first `Source:` line whose value starts with the queue folder, with
    markdown marks stripped; None when no line does."""
    for number, line in enumerate(ticket_lines, 1):
        match = SOURCE_LINE.match(MARKDOWN_MARKS.sub("", line).strip())
        if match and match.group(1).startswith(QUEUE_SOURCE_PREFIX):
            return number, match.group(1)
    return None


def queue_item_author(ticket_name, number, source_value):
    """The `generated.by` author of the queue item a `Source:` line names. Raises PlanFormatError
    (`ticket_name:line:`) naming the queue file and the expected form when the line, the file or its frontmatter
    breaks the form."""
    where = f"{ticket_name}:{number}:"
    if not QUEUE_SOURCE_FORM.match(source_value):
        raise PlanFormatError(f"{where} Source line `{source_value}` is not the queue form; expected "
                              f"`Source: {QUEUE_SOURCE_PREFIX}<slug>.md`, optionally followed by a space and text")

    queue_file = pathlib.Path(source_value.split(" ")[0]).expanduser()
    if not queue_file.is_file():
        raise PlanFormatError(f"{where} queue file {queue_file} does not exist; the Source line must name an "
                              "existing queue item (pull ~/agent-evals if the item was queued on another machine)")

    generated_value = script_utils.frontmatter_value(queue_file.read_text(), "generated")
    if generated_value is None:
        raise PlanFormatError(f"{where} queue file {queue_file} has no `generated:` frontmatter key; expected "
                              f"`{GENERATED_FORM}`")

    try:
        generated_object = json.loads(generated_value)
    except json.JSONDecodeError as error:
        raise PlanFormatError(f"{where} queue file {queue_file} `generated:` is not a JSON object ({error}); "
                              f"expected `{GENERATED_FORM}`") from error
    author = generated_object.get("by") if isinstance(generated_object, dict) else None
    if not isinstance(author, str) or not author.strip():
        raise PlanFormatError(f"{where} queue file {queue_file} `generated:` has no non-empty `by`; expected "
                              f"`{GENERATED_FORM}`")
    return author.strip()


def owner_record(ticket_path, owner, source):
    return {"owner": owner, "ticket": str(ticket_path) if ticket_path is not None else None, "source": source,
            "rule": CRITERIA_OWNER_RULES[owner]}


def criteria_owner(ticket_path):
    """{"owner", "ticket", "source", "rule"} for the ticket's criteria. A ticket whose first queue `Source:` line names
    a queue item is `session` when the item's `generated.by` is not a `human:` author, else `user`. Without one, a
    ticket with no criteria heading is `plan`, and any other ticket is `user`. A `Source:` line outside the queue
    folder never changes the owner. Raises PlanFormatError on a queue line the item cannot back, and on a ticket the
    criteria reader cannot parse."""
    ticket_name = str(ticket_path)
    ticket_text = pathlib.Path(ticket_path).read_text()
    queue_source = queue_source_line(ticket_text.splitlines())
    if queue_source is not None:
        number, source_value = queue_source
        author = queue_item_author(ticket_name, number, source_value)
        owner = CRITERIA_OWNER_USER if author.startswith(HUMAN_AUTHOR_PREFIX) else CRITERIA_OWNER_SESSION
        return owner_record(ticket_path, owner, source_value)

    try:
        ticket_criteria(ticket_text, ticket_name)
    except NoCriteriaHeadingError:
        return owner_record(ticket_path, CRITERIA_OWNER_PLAN, None)
    return owner_record(ticket_path, CRITERIA_OWNER_USER, None)


def ticket_beside(plan_path):
    """The plan folder's `00-ticket.md`, else its single `*-00-ticket.md`; None when there is none. Raises
    PlanFormatError naming the folder and the files when there are several `*-00-ticket.md` and no exact one, because
    no one of them can be picked."""
    folder = pathlib.Path(plan_path).parent
    exact_ticket = folder / "00-ticket.md"
    if exact_ticket.is_file():
        return exact_ticket
    ticket_paths = sorted(folder.glob("*-00-ticket.md"))
    if not ticket_paths:
        return None
    if len(ticket_paths) > 1:
        names = ", ".join(ticket.name for ticket in ticket_paths)
        raise PlanFormatError(f"{folder}: several tickets ({names}); keep one `*-00-ticket.md` in the plan folder")
    return ticket_paths[0]


def plan_author_criteria_missing(plan_path):
    """The names still missing for the plan author to own the criteria: `a plan.md` when the plan is not an existing
    file named `plan.md`, and `acceptance-criteria.md` when its folder lacks that file."""
    plan = pathlib.Path(plan_path)
    missing = []
    if plan.name != PLAN_ONLY_PLAN_NAME or not plan.is_file():
        missing.append(f"a {PLAN_ONLY_PLAN_NAME}")
    if not (plan.parent / CRITERIA_FILE_NAME).is_file():
        missing.append(CRITERIA_FILE_NAME)
    return missing


def plan_criteria_owner(plan_path):
    """`criteria_owner` of the ticket beside the plan. With no ticket beside it, `ticket: None` and the owner is `plan`
    when the plan is an existing file named `plan.md` and its folder holds `acceptance-criteria.md` (the plan author
    wrote the criteria), else `user`."""
    ticket_path = ticket_beside(plan_path)
    if ticket_path is None:
        author_wrote = not plan_author_criteria_missing(plan_path)
        owner = CRITERIA_OWNER_PLAN if author_wrote else CRITERIA_OWNER_USER
        return owner_record(None, owner, None)
    return criteria_owner(ticket_path)


# Ticket-criteria drift. A plan or criteria file never cuts, narrows, splits or rewords a ticket criterion without the
# user's sign-off (or, for a ticket whose criteria a session owns, the session's ruling), so each ticket criterion's
# text must be the text of some AC in acceptance-criteria.md.
SIGN_OFF = re.compile(r"sign-?off", re.I)
SESSION_RULING_MARK = re.compile(rf"{SIGN_OFF.pattern}|\bruled\b|\bruling\b", re.I)
MARKDOWN_MARKS = re.compile(r"[*_`]")


def normalized_words(text):
    """The text without markdown marks (`*`, `_`, backticks) and with each run of whitespace made one space."""
    return " ".join(MARKDOWN_MARKS.sub("", text).split())


def sign_off_names(lines, entry, mark=SIGN_OFF):
    """True when a line holds the `mark` (a sign-off by default) and names the ticket criterion: it quotes the
    criterion's text or says `Ticket #<n>`."""
    label = re.compile(rf"ticket\s*#{entry['number']}(?!\d)", re.I)
    for line in lines:
        if mark.search(line) and (normalized_words(entry["text"]) in normalized_words(line) or label.search(line)):
            return True
    return False


def ac_drift_failures(ticket_text, criteria_text, spec_text, ticket_name="00-ticket.md",
                      criteria_name=CRITERIA_FILE_NAME, owner=CRITERIA_OWNER_USER):
    """One message for each ticket criterion whose text (compared after markdown marks and whitespace are normalised)
    is the text of no AC in the criteria file, unless a line of the criteria file or of the spec's `## Plan Deviations`
    section holds a sign-off that names it. For a `session` owner, a line holding a ruling (`ruled`, `ruling`) counts
    too. A ticket with no criteria heading has nothing to drift from and gives []; any other ticket the reader cannot
    parse raises PlanFormatError (`ticket_name:line:`)."""
    try:
        ticket_entries = ticket_criteria(ticket_text, ticket_name)
    except NoCriteriaHeadingError:
        return []
    criteria_texts = {normalized_words(text) for text in criteria_by_id(criteria_text, criteria_name).values()}
    spec_lines = spec_text.splitlines()
    deviation_lines = [spec_lines[index]
                       for index in script_utils.heading_section_indexes(spec_lines, DEVIATIONS_HEADING)]
    sign_off_lines = criteria_text.splitlines() + deviation_lines
    session_owned = owner == CRITERIA_OWNER_SESSION
    mark = SESSION_RULING_MARK if session_owned else SIGN_OFF
    failures = []
    for entry in ticket_entries:
        if normalized_words(entry["text"]) in criteria_texts or sign_off_names(sign_off_lines, entry, mark):
            continue
        if session_owned:
            failures.append(f"{criteria_name}: ticket criterion {entry['number']} reads {entry['text'][:100]!r}: no AC "
                            "in the criteria file carries this wording and no sign-off or ruling names it. Copy it "
                            "verbatim into one AC, or add a line under `## Plan Deviations` that holds `ruling` and "
                            f"names `Ticket #{entry['number']}`, with who and when (in `decide`, put "
                            f"`Ticket #{entry['number']}` in `--ruling`)")
            continue
        failures.append(f"{criteria_name}: ticket criterion {entry['number']} reads {entry['text'][:100]!r}: no AC in "
                        f"the criteria file carries this wording and no sign-off names it. Copy it verbatim into one "
                        f"AC, or record the user's sign-off (who and when) naming it")
    return failures
