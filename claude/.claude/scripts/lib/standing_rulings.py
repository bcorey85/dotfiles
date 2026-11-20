"""standing_rulings.py: the one form and the one reader for a standing ruling, a user's order that covers a whole class
of criterion changes, and the test for a plan impact that only rewords a criterion.

A standing ruling is one line in the plan's `## Plan Deviations` section or in `03-decisions.md` beside the plan:

    Standing ruling by <who> at <YYYY-MM-DD>: "<the user's quoted words>" covers: rewords

`covers` is `rewords` only. A cut or a narrowing is never covered."""
import re

import plan_format
import script_utils

COVERS_REWORDS = "rewords"
STANDING_RULING_FORM = 'Standing ruling by <who> at <YYYY-MM-DD>: "<the user\'s quoted words>" covers: rewords'
STANDING_RULING_START = re.compile(r"^\s*(?:[-*]\s+)?Standing ruling\b")
STANDING_RULING_LINE = re.compile(
    r'^\s*(?:[-*]\s+)?Standing ruling by (?P<who>\S.*?) at (?P<at>\d{4}-\d\d-\d\d): "(?P<quote>.+)" '
    rf"covers: (?P<covers>{COVERS_REWORDS})\s*\.?\s*$")
# The `kind: reword` field of an impact block. It sits on its own line, or after a space or a dash when the lines of a
# reviewer's ask were joined into one.
IMPACT_KIND_LINE = re.compile(r"(?<!\w)kind[*`_]*:[ \t*`_]*(\w+)", re.I)
REWORD_KIND = "reword"


def standing_rulings_in(lines, name, indexes=None):
    """The standing rulings among the 0-based `indexes` of `lines` (all of them by default) of the file `name`, as
    [{who, at, quote, covers}]. A line that starts `Standing ruling` and does not match the form raises
    PlanFormatError (`name:line:`)."""
    rulings = []
    for index in range(len(lines)) if indexes is None else indexes:
        line = lines[index]
        number = index + 1
        if not STANDING_RULING_START.match(line):
            continue
        match = STANDING_RULING_LINE.match(line)
        if match is None:
            raise plan_format.PlanFormatError(
                f"{name}:{number}: a standing ruling line reads {line.strip()[:100]!r}; expected "
                f"`{STANDING_RULING_FORM}`")
        rulings.append(match.groupdict())
    return rulings


def standing_rulings(plan_path):
    """The standing rulings of the plan at `plan_path`: those in its `## Plan Deviations` section, then those in
    `03-decisions.md` beside it. A file that is missing has none."""
    rulings = []
    if plan_path.is_file():
        lines = plan_path.read_text().splitlines()
        section = script_utils.heading_section_indexes(lines, plan_format.DEVIATIONS_HEADING)
        rulings += standing_rulings_in(lines, str(plan_path), section)
    decisions_path = plan_path.with_name(plan_format.DECISION_LOG_NAME)
    if decisions_path.is_file():
        rulings += standing_rulings_in(decisions_path.read_text().splitlines(), str(decisions_path))
    return rulings


def reword_ruling(plan_path):
    """The first standing ruling of the plan that covers rewords, or None."""
    for ruling in standing_rulings(plan_path):
        if ruling["covers"] == COVERS_REWORDS:
            return ruling
    return None


def impact_rewords_criterion(impact_text):
    """True when every PLAN-IMPACT in the text names a criterion id on its `acceptance_criteria:` line and says
    `kind: reword`: the impact keeps the criterion and changes only its words."""
    return all(block_rewords_criterion(block) for block in impact_blocks(impact_text))


def impact_blocks(impact_text):
    """The text split at each PLAN-IMPACT opening: one block per impact. A text with no opening is one block."""
    starts = [match.start() for match in plan_format.PLAN_IMPACT_OPENING.finditer(impact_text)]
    if not starts:
        return [impact_text]
    ends = [*starts[1:], len(impact_text)]
    return [impact_text[start:end] for start, end in zip(starts, ends, strict=True)]


def block_rewords_criterion(block):
    """True when one impact block names a criterion id and every `kind:` line in it says `reword`, with at least one."""
    if not plan_format.criteria_ids(block, answers_only=True):
        return False
    kinds = [kind.lower() for kind in IMPACT_KIND_LINE.findall(block)]
    return bool(kinds) and all(kind == REWORD_KIND for kind in kinds)


def ruling_label(ruling):
    """Who and when of a standing ruling, for display text that holds no second time."""
    return f"{ruling['who']} at {ruling['at']}"
