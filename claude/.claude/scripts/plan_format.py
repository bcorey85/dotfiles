"""plan_format.py: the one reader of a plan's phase sections, its Phase Status list and its `#### Manual Verification`
sections.

Installed beside the scripts that import it, like script_utils.py. A plan file is text a person or a model wrote, so the
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
import re

import script_utils

PHASE_ID = r"(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*"
PHASE_HEADING = re.compile(rf"^(#{{2,4}})\s+Phase\s+({PHASE_ID})(?![A-Za-z0-9])")
MANUAL_HEADING = re.compile(r"^(#{1,6})\s+manual verification\b(.*)$", re.I)
SUCCESS_GROUP_HEADING = re.compile(r"^#{1,6}\s+(?:success criteria|automated verification|manual verification)\b", re.I)
LIST_ENTRY = re.compile(r"^(?:[-*]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.*)$")
NOT_APPLICABLE = re.compile(r"^(?:[-*]\s+)?N/A\b", re.I)
FOREIGN_START = ("|", ">", "<")
SECTION_LEVELS = (3, 4)
HUMAN_ONLY_MARK = "human-only"
AGENT_VERIFIED_MARK = "agent-verified"


PHASE_STATUS_LINE = re.compile(rf"^[-*]\s+\[( |x|X|-)\]\s+Phase\s+({PHASE_ID})\s*[:.—–-]\s*(.*)$")
MOVED_MARK = "-"
MOVED_TARGET = re.compile(r"(?i:moved to)\s+([A-Z][A-Z0-9]*-\d+)(?![A-Za-z0-9])")
DEVIATIONS_HEADING = "Plan Deviations"
STATUS_ITEM_START = re.compile(r"^[-*]\s+\[")
RISK_MARK = re.compile(r"\(risk:\s*(low|high)\)", re.I)
GATE_CLAUSE = re.compile(r"(?:^|\s)[—–-]\s*gate:\s*(.*)$", re.I)
UNSTATED_GATE = "(no condition written)"


def gate_condition(title):
    """The text of a `gate: <condition>` clause in a Phase Status title, or None when the title has no clause. The risk
    mark is not part of the condition. A clause with no text gives UNSTATED_GATE. The reader only reports the text: it
    never judges whether the condition holds."""
    clause = GATE_CLAUSE.search(title)
    if not clause:
        return None
    return RISK_MARK.sub("", clause.group(1)).strip() or UNSTATED_GATE


class PlanFormatError(Exception):
    """A line the grammar does not parse. The message starts with `name:line:`."""


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
    firstLines = {}
    current = None

    for index, line in enumerate(lines):
        if index in fenced:
            continue
        heading = script_utils.MARKDOWN_HEADING.match(line)
        if not heading:
            continue

        level = len(heading.group(1))
        if current is not None and level <= current["level"] and not SUCCESS_GROUP_HEADING.match(line):
            current["end"] = index
            current = None

        phaseHeading = PHASE_HEADING.match(line)
        if not phaseHeading:
            continue

        sectionId = phaseHeading.group(2)
        if current is not None and level > current["level"] and sectionId in firstLines:
            continue

        if current is not None:
            current["end"] = index
        current = {"start": index, "level": level, "title": line[phaseHeading.end():].lstrip(" :.—–-"),
                   "end": len(lines)}
        spans.append((sectionId, current))
        if sectionId in firstLines:
            failures.append({"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {sectionId} has two "
                             f"sections, on line {firstLines[sectionId] + 1} and line {index + 1}. Give "
                             "each phase its own id."})
            continue
        firstLines[sectionId] = index
    return spans, failures


def phase_section(lines, phaseId):
    """The first section of the phase with this exact id as {"start", "level", "title", "end"}, or None."""
    spans, _ = phase_spans(lines)
    return next((section for sectionId, section in spans if sectionId == phaseId), None)


def phase_status_entries(lines, closing_skill):
    """The `- [ ] Phase <id>: <title>` lines under the `Phase Status` heading, in file order, and the failures for a
    list line that does not parse or an id listed twice. `closing_skill(title)` names the skill a closing phase runs,
    or None. Each entry is {"line", "done", "number", "title", "risk", "closing", "gate"}; "gate" is the text of a
    `gate: <condition>` clause in the title, or None. "moved" is True for a `[-]` line and "movedTo" is the ticket key
    its `moved to <KEY>` names, or None; a moved phase is not "done". "open" is True for a phase that is neither done
    nor moved: the phases a run can still start. A `[-]` line with no `moved to <KEY>` is a failure and still returns
    its entry."""
    fenced = script_utils.fenced_line_indexes(lines)
    entries = []
    failures = []
    firstLines = {}
    inStatus = False

    for index, line in enumerate(lines):
        if index in fenced:
            continue
        heading = script_utils.MARKDOWN_HEADING.match(line)
        if heading:
            inStatus = heading.group(2).strip() == "Phase Status"
            continue
        if not inStatus or not STATUS_ITEM_START.match(line):
            continue

        match = PHASE_STATUS_LINE.match(line)
        if not match:
            failures.append({"line": index + 1, "kind": "unparsed-line", "detail": f"{line.strip()!r}. Rewrite it as "
                             "`- [ ] Phase <id>: <title>`, or move it out of the section."})
            continue

        number = match.group(2)
        if number in firstLines:
            failures.append({"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {number} twice, on line "
                             f"{firstLines[number] + 1} and line {index + 1}. Give each phase its own id."})
            continue

        firstLines[number] = index
        title = match.group(3)
        risk = RISK_MARK.search(title)
        closing = closing_skill(title)
        isMoved = match.group(1) == MOVED_MARK
        target = MOVED_TARGET.search(title) if isMoved else None
        if isMoved and not target:
            failures.append({"line": index + 1, "kind": "moved-without-target", "detail": f"Phase {number} is marked "
                             "`[-]` (moved to another ticket) but the line does not say `moved to <KEY>`. Add the "
                             "ticket key, for example `moved to LED-16`."})
        isDone = match.group(1) in ("x", "X")
        entries.append({"line": index, "done": isDone, "moved": isMoved, "open": not isDone and not isMoved,
                        "movedTo": target.group(1) if target else None, "number": number, "title": title,
                        "risk": risk.group(1).lower() if risk else "high", "closing": closing,
                        "gate": gate_condition(title)})
    return entries, failures


def deviation_records_move(lines, number, ticketKey):
    """True when one line of the plan's `## Plan Deviations` section names the phase and names the ticket key it moved
    to. The phase is named `Phase <id>` or `P<id>`, not followed by more of an id; an id that already starts with `P` is
    also named by itself (`P4`, `Phase P4`). The key must stand alone (`LED-16`, not `LED-160`). A line that names only
    the phase, such as a tick entry, does not count. The check only finds the words; it never judges who signed."""
    deviationLines = [lines[index] for index in script_utils.heading_section_indexes(lines, DEVIATIONS_HEADING)]
    escaped = re.escape(number)
    bareName = escaped if number.startswith("P") else "P" + escaped
    phaseName = re.compile(rf"(?<![A-Za-z0-9])(?:Phase\s+{escaped}|{bareName})(?![A-Za-z0-9]|[.-][A-Za-z0-9])")
    keyName = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ticketKey)}(?![A-Za-z0-9])")
    return any(phaseName.search(line) and keyName.search(line) for line in deviationLines)


def moved_deviation_failure(lines, entry):
    """The `moved-without-deviation` failure for a moved entry whose ticket key no Plan Deviations line records with
    the phase's name, or None. A moved entry with no key has its own failure and gives None here."""
    if not entry["moved"] or entry["movedTo"] is None:
        return None
    if deviation_records_move(lines, entry["number"], entry["movedTo"]):
        return None
    return {"line": entry["line"] + 1, "kind": "moved-without-deviation", "detail": f"Phase {entry['number']} is "
            f"marked moved, but '## {DEVIATIONS_HEADING}' has no line that names it and {entry['movedTo']}. Record "
            f"the sign-off for the move in {DEVIATIONS_HEADING} (who, when, their words), and name Phase "
            f"{entry['number']} and {entry['movedTo']} in the same line."}


def parse_plan(lines, closing_skill=lambda title: None):
    """The plan's Phase Status entries and phase sections, with every failure sorted by line: {"entries", "sections"
    (id to the first section of that id), "failures"}. A Phase Status entry with no section is a failure unless it is
    a closing phase or a moved phase, and a section with no Phase Status entry is a failure when the plan lists any phase."""
    entries, failures = phase_status_entries(lines, closing_skill)
    spans, sectionFailures = phase_spans(lines)
    failures += sectionFailures

    sections = {}
    for sectionId, section in spans:
        sections.setdefault(sectionId, section)

    for entry in entries:
        deviationFailure = moved_deviation_failure(lines, entry)
        if deviationFailure:
            failures.append(deviationFailure)

        # A closing phase is defined by its skill, so its Phase Status line needs no section of its own. A moved phase
        # may take its section to the new ticket.
        if entry["number"] not in sections and not entry["closing"] and not entry["moved"]:
            failures.append({"line": entry["line"] + 1, "kind": "missing-section", "detail": f"Phase "
                             f"{entry['number']} is in Phase Status but the plan has no '## Phase {entry['number']}' "
                             "section."})

    statusIds = {entry["number"] for entry in entries}
    for number, section in sections.items():
        if entries and number not in statusIds:
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
    entries, entryFailures = phase_status_entries(lines, lambda title: None)
    moved = [entry for entry in entries if entry["moved"]]
    failures = [failure for failure in entryFailures if failure["kind"] == "moved-without-target"]
    deviationFailures = [moved_deviation_failure(lines, entry) for entry in moved]
    failures += [failure for failure in deviationFailures if failure]
    if failures:
        first = min(failures, key=lambda failure: failure["line"])
        raise PlanFormatError(f"{name}:{first['line']}: {first['detail']}")
    return moved


def phase_at(spans, index):
    """The id of the phase section that holds this 0-based line index, or None."""
    return next((sectionId for sectionId, section in spans if section["start"] <= index < section["end"]), None)


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
    items = []
    inSection = False
    sectionLevel = 0
    deeperHeading = None
    qualifier = ""
    last = None

    for index, line in enumerate(lines):
        number = index + 1
        isFenced = index in fenced
        heading = None if isFenced else script_utils.MARKDOWN_HEADING.match(line)

        if not isFenced and line.strip() == "---":
            inSection = False
            last = None
        if heading:
            level = len(heading.group(1))
            last = None
            manual = MANUAL_HEADING.match(line)
            if manual:
                if level not in SECTION_LEVELS:
                    raise PlanFormatError(f"{name}:{number}: a Manual Verification heading must be level 3 or level "
                                          f"4 (`### Manual Verification` or `#### Manual Verification`): "
                                          f"{line.strip()[:80]}")
                if not inSection or level <= sectionLevel:
                    sectionLevel = level
                inSection = True
                qualifier = manual.group(2)
                deeperHeading = None
            elif inSection and level > sectionLevel:
                deeperHeading = line.strip()[:80]
            else:
                inSection = False
            continue

        if not inSection:
            continue
        if isFenced:
            raise PlanFormatError(f"{name}:{number}: a fenced block inside Manual Verification; write each step "
                                  f"as a list item: {line.strip()[:80]}")
        if not line.strip():
            continue

        if line[0] in " \t":
            if last is None:
                raise PlanFormatError(f"{name}:{number}: indented line with no list item above it in Manual "
                                      f"Verification: {line.strip()[:80]}")
            last["text"] += " " + line.strip()
            continue

        entry = LIST_ENTRY.match(line)
        if entry and deeperHeading:
            raise PlanFormatError(f"{name}:{number}: a list item under the sub-heading `{deeperHeading}` inside Manual "
                                  f"Verification; if that heading starts a new section, give it the Manual Verification "
                                  f"heading's level or a higher one, otherwise move the item above it: "
                                  f"{line.strip()[:80]}")
        if entry and (entry.group(1) is not None or not NOT_APPLICABLE.match(line)):
            last = {"phase": phase_at(spans, index), "text": entry.group(2).strip(),
                    "checked": (entry.group(1) or "").lower() == "x", "line": number, "heading": qualifier}
            items.append(last)
            continue

        last = None
        if line.startswith(FOREIGN_START):
            raise PlanFormatError(f"{name}:{number}: line shape not allowed in Manual Verification (table, quote or "
                                  f"HTML): {line.strip()[:80]}")

    for item in items:
        item["humanOnly"] = HUMAN_ONLY_MARK in item["heading"].lower() or HUMAN_ONLY_MARK in item["text"].lower()
        item["verified"] = item["checked"] or (not item["humanOnly"] and AGENT_VERIFIED_MARK in item["text"].lower())
    return items
