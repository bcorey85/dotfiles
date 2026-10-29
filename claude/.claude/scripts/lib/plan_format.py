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
import pathlib
import re

import script_utils

DONE_PREFIX = "- Done: "
# A `path/with/a/folder.ext` in backticks, with an optional :line or :start-end suffix inside the ticks.
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
PHASE_ID = r"(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*"
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
# bracketed tags, in either order.
PLAN_CHANGE_MARK = re.compile(r"(?:(?:`?[\w./-]+\.\w+:\d+`?|\[[\w-]+\])[\s—\N{EN DASH}:-]*)*plan[-_ ]?impact", re.I)
# A PLAN-IMPACT's `acceptance_criteria:` line: `none`, or the criteria the change would alter.
AC_CHANGE_LINE = re.compile(r"acceptance[_ ]criteria[*`_]*:[ \t*`_]*([^;\n]*)", re.I)
PLAN_IMPACT_OPENING = re.compile(r"plan[-_ ]?impact(?![*`_]*:[ \t*`_]*yes\b)", re.I)
BELOW_CRITERIA_RULING = ("No acceptance criterion changes, so the code wins: the plan follows the code. Adopted by "
                         "rule; no one was asked.")
PLAN_IMPACT_HEADER_WORD = re.compile(r"[*`_]*plan[-_ ]?impact[*`_]*[ \t]*:", re.I)
# The `acceptance_criteria:` clause with the marks and separators before it, so removing it leaves no stray dash.
AC_CHANGE_CLAUSE = re.compile(r"[\s;,—\N{EN DASH}-]*[*`_]*" + AC_CHANGE_LINE.pattern, re.I)
DEVIATION_ENTRY = re.compile(rf"^- \d{{4}}-\d\d-\d\d(?: \(Phase ({PHASE_ID})\))?:")
DEVIATION_RULING_PREFIX = "  The ruling: "
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


class NoCriteriaHeadingError(PlanFormatError):
    """A ticket with no `## Acceptance*` or `## Requirements*` heading."""


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
        if current is not None and level <= current["level"] and not SUCCESS_GROUP_HEADING.match(line):
            current["end"] = index
            current = None

        phase_heading = PHASE_HEADING.match(line)
        if not phase_heading:
            continue

        section_id = phase_heading.group(2)
        if current is not None and level > current["level"] and section_id in first_lines:
            continue

        if current is not None:
            current["end"] = index
        current = {"start": index, "level": level, "title": line[phase_heading.end():].lstrip(" :.—–-"),
                   "end": len(lines)}
        spans.append((section_id, current))
        if section_id in first_lines:
            failures.append({"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {section_id} has two "
                             f"sections, on line {first_lines[section_id] + 1} and line {index + 1}. Give "
                             "each phase its own id."})
            continue
        first_lines[section_id] = index
    return spans, failures


def phase_section(lines, phase_id):
    """The first section of the phase with this exact id as {"start", "level", "title", "end"}, or None."""
    spans, _ = phase_spans(lines)
    return next((section for section_id, section in spans if section_id == phase_id), None)


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
            failures.append({"line": index + 1, "kind": "duplicate-id", "detail": f"Phase {number} twice, on line "
                             f"{first_lines[number] + 1} and line {index + 1}. Give each phase its own id."})
            continue

        first_lines[number] = index
        title = match.group(3)
        risk = RISK_MARK.search(title)
        closing = closing_skill(title)
        is_moved = match.group(1) == MOVED_MARK
        target = MOVED_TARGET.search(title) if is_moved else None
        if is_moved and not target:
            failures.append({"line": index + 1, "kind": "moved-without-target", "detail": f"Phase {number} is marked "
                             "`[-]` (moved to another ticket) but the line does not say `moved to <KEY>`. Add the "
                             "ticket key, for example `moved to LED-16`."})
        is_done = match.group(1) in ("x", "X")
        entries.append({"line": index, "done": is_done, "moved": is_moved, "open": not is_done and not is_moved,
                        "movedTo": target.group(1) if target else None, "number": number, "title": title,
                        "risk": risk.group(1).lower() if risk else "high", "closing": closing,
                        "gate": gate_condition(title)})
    return entries, failures


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
            manual_heading_step(scan, line, len(heading.group(1)), name, number)
            continue
        if scan["in_section"]:
            manual_line_step(scan, line, is_fenced, name, (number, phase_at(spans, index)))

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
PLAN_FILES_GLOB = "docs/plans/*/spec.md"
GATE_ENV_HINT = "(Put these variables before every test, check or build command you run.)"

# An Automated Verification item that says there is nothing to run: "- [ ] N/A — docs only", "- [ ] none".
# A bold label may come first when the word after it is N/A: "- [ ] **Test-verified**: N/A on the machines."
NO_AUTOMATED_CHECK = re.compile(r"^- \[[ x]\]\s*(?:[*_`]*\s*(?:n/a|none)\b|\*\*[^*]+\*\*:?\s*n/a\b)", re.IGNORECASE)

# An Automated Verification item that the code step never runs because the plan says another place does:
# "- [ ] **CI-verified**: the pipeline runs it", "- [ ] Human-only: look at the page". A bold label may come first.
DEFERRED_VERIFICATION = re.compile(r"^- \[[ x]\]\s*(?:\*\*[^*]+\*\*:?\s*)?[*_`]*\s*(?P<tag>ci-verified|human-only)\b",
                                   re.IGNORECASE)
DEFERRED_TAG_NAMES = {"ci-verified": "CI-verified", "human-only": "human-only"}


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
            inside = line.startswith(AUTOMATED_HEADING)
            lowered = line.lower()
            misworded = "automated" in lowered and "verif" in lowered and not MANUAL_HEADING.match(line)
            if strict and not inside and misworded:
                raise PlanFormatError(
                    f"{name}:{first_line + index}: heading `{line.strip()}` is not a verification heading; "
                    f"rename it to `{AUTOMATED_HEADING}` for commands, or `#### Manual Verification:` for human "
                    f"checks, or its items are not read"
                )
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
    """"CI-verified" or "human-only" for an Automated Verification item tagged that way, else None."""
    tag_match = DEFERRED_VERIFICATION.match(line)
    return DEFERRED_TAG_NAMES[tag_match.group("tag").lower()] if tag_match else None


def runs_no_command(line):
    """True for an Automated Verification item that gets no command run: it says N/A or none, or it is left to CI or
    a person."""
    return bool(NO_AUTOMATED_CHECK.match(line) or deferred_verification_tag(line))


OPEN_BOX = re.compile(r"^- \[ \]")
SUCCESS_BOLD_LABEL = re.compile(r"^\*\*success criteria\b", re.I)
BOLD_LABEL_LINE = re.compile(r"^\*\*[^*]+\*\*:?\s*$")
SUCCESS_OR_AUTOMATED_HEADING = re.compile(r"^#{1,6}\s+(?:success criteria|automated verification)\b", re.I)


def open_success_items(lines):
    """The `- [ ]` items under a phase's Success Criteria that need evidence, in file order, as {"index": the 0-based
    line of the item, "end": the index after its indented continuation lines, "text": the item's words with its
    continuation lines folded in}. Items under Manual Verification, tagged CI-verified or human-only, and N/A items are
    left out, and so are items in fenced blocks. `lines` is one phase's section."""
    fenced = script_utils.fenced_line_indexes(lines)
    items = []
    inside = False

    for index, line in enumerate(lines):
        if index in fenced:
            continue
        if script_utils.MARKDOWN_HEADING.match(line):
            inside = bool(SUCCESS_OR_AUTOMATED_HEADING.match(line))
            continue
        if BOLD_LABEL_LINE.match(line):
            inside = bool(SUCCESS_BOLD_LABEL.match(line))
            continue
        if line.strip() == "---":
            inside = False
            continue
        if not (inside and OPEN_BOX.match(line)) or runs_no_command(line):
            continue

        end = index + 1
        while end < len(lines) and lines[end].strip() and lines[end][0] in " \t" and end not in fenced:
            end += 1
        folded = " ".join(part.strip() for part in lines[index:end])
        items.append({"index": index, "end": end, "text": automated_item_text(folded)})
    return items


def write_item_evidence(lines, items, evidence):
    """`lines` with each open item's box checked and a `  - Done: <evidence>` line under it (after its continuation
    lines). `items` come from open_success_items(lines); `evidence` has one text per item, in the same order."""
    written = list(lines)
    for item, text in reversed(list(zip(items, evidence, strict=True))):
        written.insert(item["end"], f"  {DONE_PREFIX}{text}")
        written[item["index"]] = written[item["index"]].replace("[ ]", "[x]", 1)
    return written


def gate_env(plan_text):
    """The `NAME=value` words that the plan's Automated Verification commands start with, one per name, in file order.
    An item that says N/A or is left to CI or a person is not a command that gets run, so it gives none."""
    verification_items = automated_verification_rows(plan_text.splitlines())
    runnable_items = [line for _, line in verification_items if not runs_no_command(line)]
    spans = [span for line in runnable_items for span in script_utils.backticked_spans(line)]
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


def repo_gate_env(repo_root, plan_rel=None):
    """The environment variables the repo's gate commands need: what `gate_env` reads from the plans under
    docs/plans/*/spec.md. A run whose own plan `planRel` (a path under repoRoot) is readable gets only that plan's
    names. A run with no readable plan takes a name the other plans set when they all give it the same value; a name
    they give different values is left out, since no plan says which one this run needs."""
    root = pathlib.Path(repo_root)

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

    chosen = {}
    for assignment in gate_env(own_text):
        chosen[assignment.split("=", 1)[0]] = assignment
    return list(chosen.values())


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
]


def closing_skill(title):
    """The skill a closing phase's title names (`Verify pass` names /verify-branch), or None for any other title."""
    return next((skill for pattern, skill in CLOSING_PHASES if pattern.search(title)), None)


def parse_plan_with_closing_phases(plan_lines):
    """parse_plan with the closing phases recognised by their titles."""
    return parse_plan(plan_lines, closing_skill)


def phase_text(plan_lines, number):
    """The text of the phase's section, or None when the plan has no section for it."""
    section = phase_section(plan_lines, number)
    if section is None:
        return None
    return "\n".join(plan_lines[section["start"]:section["end"]])


def phase_wording(text):
    """A phase section's text without what a run writes into it: checked boxes read as open and the `Done:` evidence
    lines are dropped. Two sections with the same wording say the same thing to a coder."""
    done_marker = DONE_PREFIX.rstrip()
    lines = [re.sub(r"^(\s*[-*] )\[[xX]\]", r"\1[ ]", line) for line in text.split("\n")
             if not line.strip().startswith(done_marker)]
    return "\n".join(line.rstrip() for line in lines).strip()


def ordered_pending(entries):
    """The open phases, with the closing phases after the rest."""
    pending = [entry for entry in entries if entry["open"]]
    return [e for e in pending if not e["closing"]] + [e for e in pending if e["closing"]]


def gate_blockers(pending):
    """A run never starts a phase past an open gated one. The gated open phases ahead of the first open phase without
    a gate, and that phase (None when every open phase is gated)."""
    next_ungated = next((entry for entry in pending if not entry["gate"]), None)
    gated_ahead = pending[:pending.index(next_ungated)] if next_ungated else pending
    return gated_ahead, next_ungated


def gated_phase_text(entries):
    return "; ".join(f"Phase {entry['number']} (gate: {entry['gate']})" for entry in entries)


def gate_block_text(gated_ahead, next_ungated):
    gated_text = gated_phase_text(gated_ahead)
    text = f"open phases with a gate clause come first: {gated_text}. The script does not judge a gate."
    if next_ungated:
        text += f" The next open phase without a gate is Phase {next_ungated['number']}."
    return text + " `start --phase <id>` runs one anyway."


def moved_phase_text(entries):
    return ", ".join(f"Phase {entry['number']} to {entry['movedTo']}" for entry in entries if entry["moved"])


def moved_phase_stop(entry, plan_name, coder_ran=False):
    """The stop text for a phase that is moved to another ticket. coder_ran is True when the phase became moved after
    its coder was dispatched."""
    if coder_ran:
        ran_text = "The coder ran, and its work is not marked done or committed."
    else:
        ran_text = "No coder was dispatched."
    return (f"Phase {entry['number']} is moved to {entry['movedTo']} in {plan_name}, so this plan does not run it. "
            f"{ran_text} Tell the user; the phase is worked under {entry['movedTo']}.")


def mark_phase_done(plan_path, number):
    """Check the phase's Phase Status line in the plan file when the phase is open."""
    plan_lines = plan_path.read_text().split("\n")
    entries = parse_plan_with_closing_phases(plan_lines)["entries"]
    entry = next((e for e in entries if e["number"] == number and e["open"]), None)
    if entry:
        plan_lines[entry["line"]] = plan_lines[entry["line"]].replace("[ ]", "[x]", 1)
    plan_path.write_text("\n".join(plan_lines))


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
    impacts = max(1, len(PLAN_IMPACT_OPENING.findall(impact)))
    return len(answers) < impacts or any(answer != "none" for answer in answers)


def below_criteria_summary(impact):
    """What the plan assumed and what the code does, on one line."""
    without_marks = PLAN_IMPACT_HEADER_WORD.sub(" ", impact)
    disagreement = AC_CHANGE_CLAUSE.sub(" ", without_marks)
    return script_utils.one_line(disagreement, limit=400).strip(" ;,—-")


def below_criteria_ruling(impact):
    """The ruling for a plan change that changes no acceptance criterion, with its summary."""
    return f"{BELOW_CRITERIA_RULING} {below_criteria_summary(impact)}"


def below_criteria_deviations(plan_text, phase=None):
    """The disagreement of each `## Plan Deviations` entry the below-criteria rule adopted, of one phase or, with no
    phase, of all, as `Phase <id>: <disagreement>`."""
    ruling_start = DEVIATION_RULING_PREFIX + BELOW_CRITERIA_RULING
    entry_phase = None
    deviations = []
    lines = plan_text.splitlines()
    for index in script_utils.heading_section_indexes(lines, DEVIATIONS_HEADING):
        line = lines[index]
        entry = DEVIATION_ENTRY.match(line)
        if entry:
            entry_phase = entry.group(1)
            continue
        if not line.startswith(ruling_start):
            continue
        if phase is not None and entry_phase != str(phase):
            continue

        summary = line[len(ruling_start):].strip()
        deviations.append(f"Phase {entry_phase}: {summary}" if entry_phase else summary)
    return deviations


def ruling_owner(repo_dir, by):
    """Who a plan-impact ruling is signed by: the git user name for `--by user`, the session otherwise."""
    if by != "user":
        return SESSION_RULING_OWNER
    return script_utils.git_output(repo_dir, "config", "user.name") or "the user"


PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")
DECIDE_USAGE_STEM = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'


def is_ruling_by(by):
    """True when a `--by` value names who ruled: the user or the session."""
    return by in ("user", "session")


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


def reopen_closing_phases(plan_path):
    """Uncheck every done closing phase in the plan file; the numbers of the phases it unchecked."""
    plan_lines = plan_path.read_text().split("\n")
    reopened = [e for e in parse_plan_with_closing_phases(plan_lines)["entries"] if e["closing"] and e["done"]]
    for entry in reopened:
        plan_lines[entry["line"]] = re.sub(r"\[[xX]\]", "[ ]", plan_lines[entry["line"]], count=1)
    plan_path.write_text("\n".join(plan_lines))
    return [entry["number"] for entry in reopened]


def plan_failure_rows(plan, plan_name):
    return [f"{plan_name}:{f['line']}: {f['kind']}: {f['detail']}" for f in plan["failures"]]


def plan_failure_message(plan, plan_name):
    rows = plan_failure_rows(plan, plan_name)
    return "The plan's Phase Status does not parse. Report each line to the user and stop:\n" + "\n".join(rows)


def plan_mid_edit_message(plan, plan_name):
    """The message for a plan whose failures are all kinds a renumber passes through one Edit at a time."""
    rows = plan_failure_rows(plan, plan_name)
    return ("The plan does not parse yet. It may be mid-edit, for example renumbering phase headings one Edit at a "
            "time. Finish the edits and re-check after the last Edit. If the error is still "
            "there then, report these lines to the user and stop:\n" + "\n".join(rows))


def phase_manual_items(plan_lines, number, plan_name):
    """The Manual Verification items of one phase (all phases when number is None). The grammar reads the whole plan,
    so a PlanFormatError names the line in the file."""
    items = manual_verification("\n".join(plan_lines), plan_name)
    if number is None:
        return items
    return [item for item in items if item["phase"] == str(number)]


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


def criteria_by_id(criteria_text, name="acceptance-criteria.md"):
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
    return set(CONTENT_WORD.findall(text.lower())) - AC_STOP_WORDS


def missing_criteria_failure(spec_path):
    """The one row for a spec with an Acceptance Criteria section whose acceptance-criteria.md beside it is missing
    or empty, else None. Run by `plan check --final` and by `/code` start; plain `plan check` skips it because the
    criteria file is written after the spec."""
    has_criteria_section = any(ACCEPTANCE_HEADING.match(line) for line in spec_path.read_text().splitlines())
    if not has_criteria_section:
        return None

    criteria_path = spec_path.with_name("acceptance-criteria.md")
    if criteria_path.is_file() and criteria_path.read_text().strip():
        return None
    return (f"{criteria_path}: missing or empty, and the spec has an Acceptance Criteria section. The spec-criteria "
            "step never ran: dispatch spec-criteria (eng-spec Phase 6, step 17), never write the file yourself.")


def spec_ac_failures(spec_path):
    """The finalization rows for a file named spec.md: the ac_reference_failures rows read against the
    acceptance-criteria.md beside it (a missing file is None) and the ac_drift_failures rows against the ticket beside
    it (checked only when both the ticket and the criteria file exist). Any other file name gives []. A criteria file
    with a repeated id gives its one error row. A ticket with no criteria heading is not checked for drift."""
    if spec_path.name != "spec.md":
        return []
    spec_text = spec_path.read_text()
    failures = []
    criteria_path = spec_path.with_name("acceptance-criteria.md")
    criteria_text = criteria_path.read_text() if criteria_path.is_file() else None
    ticket_paths = sorted(spec_path.parent.glob("*00-ticket.md"))
    try:
        failures += ac_reference_failures(spec_text, criteria_text, str(spec_path), str(criteria_path))
        if criteria_text is not None and len(ticket_paths) == 1:
            failures += ac_drift_failures(ticket_paths[0].read_text(), criteria_text, spec_text, str(ticket_paths[0]),
                                          str(criteria_path))
    except PlanFormatError as error:
        failures.append(str(error))
    return failures


def ac_reference_failures(spec_text, criteria_text, spec_name="spec.md", criteria_name="acceptance-criteria.md"):
    """One `name:line: message` string for each bare `AC<n>` in the spec that does not name criterion n of the
    criteria file. `criteria_text` None means the criteria file does not exist, so every bare reference fails. A
    reference written `ticket AC<n>` is never checked. Fenced blocks are skipped. The line holding the reference, and
    the line after it, must share at least MIN_SHARED_WORDS content words with the criterion."""
    criteria = criteria_by_id(criteria_text, criteria_name) if criteria_text is not None else {}
    lines = spec_text.splitlines()
    fenced = script_utils.fenced_line_indexes(lines)
    failures = []
    for index, line in enumerate(lines):
        if index in fenced:
            continue
        nearby = content_words(" ".join(lines[index:index + 2]))
        for reference in AC_REFERENCE.finditer(line):
            if reference.group("ticket"):
                continue
            criterion_id = f"AC{reference.group('number')}"
            where = f"{spec_name}:{index + 1}:"
            if criterion_id not in criteria:
                failures.append(f"{where} {criterion_id} is not an id in {criteria_name}; write "
                                f"`ticket {criterion_id}` for the ticket's number, or cite the criteria file's id")
            elif len(nearby & content_words(criteria[criterion_id])) < MIN_SHARED_WORDS:
                failures.append(f"{where} {criterion_id} shares no wording with {criterion_id} in {criteria_name} "
                                f"({criteria[criterion_id][:60]!r}); it may be the ticket's number. Write "
                                f"`ticket {criterion_id}`, or name the criterion's behavior beside it")
    return failures


# The ticket's acceptance criteria. verify-prep, verify-log and the plan check all read them through ticket_criteria.
AC_HEADING = re.compile(r"^(#{2,3})\s+(?:acceptance(?:\s+criteria)?|requirements)\s*:?\s*$", re.I)
AC_HEADING_LOOSE = re.compile(r"^(#{2,3})\s+(?:acceptance|requirements)\b", re.I)
LISTITEM = re.compile(r"^(\s*)(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$")


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
        if match and len(match.group(1)) < 2:
            items.append(match.group(2).strip())
        elif match and items:
            items[-1] += " " + match.group(2).strip()
        elif line.strip() and line.startswith((" ", "\t")) and items:
            items[-1] += " " + line.strip()
    return items


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


# Ticket-criteria drift. A plan or criteria file never cuts, narrows, splits or rewords a ticket criterion without the
# user's sign-off, so each ticket criterion's text must be the text of some AC in acceptance-criteria.md.
SIGN_OFF = re.compile(r"sign-?off", re.I)
MARKDOWN_MARKS = re.compile(r"[*_`]")


def normalized_words(text):
    """The text without markdown marks (`*`, `_`, backticks) and with each run of whitespace made one space."""
    return " ".join(MARKDOWN_MARKS.sub("", text).split())


def sign_off_names(lines, entry):
    """True when a line holds a sign-off and names the ticket criterion: it quotes the criterion's text or says
    `Ticket #<n>`."""
    label = re.compile(rf"ticket\s*#{entry['number']}(?!\d)", re.I)
    for line in lines:
        if SIGN_OFF.search(line) and (normalized_words(entry["text"]) in normalized_words(line) or label.search(line)):
            return True
    return False


def ac_drift_failures(ticket_text, criteria_text, spec_text, ticket_name="00-ticket.md",
                      criteria_name="acceptance-criteria.md"):
    """One message for each ticket criterion whose text (compared after markdown marks and whitespace are normalised)
    is the text of no AC in the criteria file, unless a line of the criteria file or of the spec's `## Plan Deviations`
    section holds a sign-off that names it. A ticket with no criteria heading has nothing to drift from and gives [];
    any other ticket the reader cannot parse raises PlanFormatError (`ticket_name:line:`)."""
    try:
        ticket_entries = ticket_criteria(ticket_text, ticket_name)
    except NoCriteriaHeadingError:
        return []
    criteria_texts = {normalized_words(text) for text in criteria_by_id(criteria_text, criteria_name).values()}
    spec_lines = spec_text.splitlines()
    deviation_lines = [spec_lines[index]
                       for index in script_utils.heading_section_indexes(spec_lines, DEVIATIONS_HEADING)]
    sign_off_lines = criteria_text.splitlines() + deviation_lines
    failures = []
    for entry in ticket_entries:
        if normalized_words(entry["text"]) in criteria_texts or sign_off_names(sign_off_lines, entry):
            continue
        failures.append(f"{criteria_name}: ticket criterion {entry['number']} reads {entry['text'][:100]!r}: no AC in "
                        f"the criteria file carries this wording and no sign-off names it. Copy it verbatim into one "
                        f"AC, or record the user's sign-off (who and when) naming it")
    return failures
