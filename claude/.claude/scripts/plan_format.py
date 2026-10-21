"""plan_format.py: the one reader of a plan's `#### Manual Verification` sections.

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
"""
import re

import script_utils

PHASE_ID = r"(?=[A-Za-z0-9.-]*\d)[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*"
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
PHASE_HEADING = re.compile(rf"^(#{{2,4}})\s+Phase\s+({PHASE_ID})(?![A-Za-z0-9])")
MANUAL_HEADING = re.compile(r"^(#{1,6})\s+manual verification\b(.*)$", re.I)
SUCCESS_GROUP_HEADING = re.compile(r"^#{1,6}\s+(?:success criteria|automated verification|manual verification)\b", re.I)
LIST_ENTRY = re.compile(r"^(?:[-*]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.*)$")
NOT_APPLICABLE = re.compile(r"^(?:[-*]\s+)?N/A\b", re.I)
FOREIGN_START = ("|", ">", "<")
SECTION_LEVELS = (3, 4)
HUMAN_ONLY_MARK = "human-only"
AGENT_VERIFIED_MARK = "agent-verified"


class PlanFormatError(Exception):
    """A line the grammar does not parse. The message starts with `name:line:`."""


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
    items = []
    phase = None
    phaseLevel = 0
    inSection = False
    sectionLevel = 0
    deeperHeading = None
    qualifier = ""
    last = None

    for index, line in enumerate(lines):
        number = index + 1
        isFenced = index in fenced
        heading = None if isFenced else HEADING.match(line)

        if not isFenced and line.strip() == "---":
            inSection = False
            last = None
        if heading:
            level = len(heading.group(1))
            last = None
            phaseMatch = PHASE_HEADING.match(line)
            if phaseMatch:
                phase = phaseMatch.group(2)
                phaseLevel = level
            elif level <= phaseLevel and not SUCCESS_GROUP_HEADING.match(line):
                phase = None
                phaseLevel = 0
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
            last = {"phase": phase, "text": entry.group(2).strip(), "checked": (entry.group(1) or "").lower() == "x",
                    "line": number, "heading": qualifier}
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
