"""review_asks.py: the ask ids, ask outcome rows, numbered ask listing and nvim-jump anchors of a review packet,
for /review (review_fix.py) and /code (code_step_review.py).
A plan-impact ask is not a finding: it gets no id and logs no outcome row."""
import pathlib
import re
import shutil
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
from script_utils import ask_text, hanging_indent_lines, one_line, run_command

ASK_OUTCOMES = ("accepted", "rejected", "modified")
JUMP_NOTE_LIMIT = 160
# One path with a line or line range and nothing else: a list of locations or a bare path has no one place to jump to.
JUMP_ANCHOR = re.compile(r"^[^\s,;]+:\d+(-\d+)?$")


def jump_anchor_args(asks):
    """The nvim-jump arguments for the asks: `--note <question> <path:line>` for each ask whose file_line is one
    well-formed anchor. Empty when no ask has one."""
    arguments = []
    for item in asks:
        file_line = item.get("file_line") or ""
        if JUMP_ANCHOR.match(file_line):
            arguments += ["--note", one_line(item.get("question", ""), JUMP_NOTE_LIMIT), file_line]
    return arguments


def run_nvim_jump(command, asks, cwd=None):
    """Run the nvim-jump `command` once over the asks' anchors and return a line saying what happened."""
    arguments = jump_anchor_args(asks)
    if not arguments:
        return "no ask names a file:line: nothing to jump to."
    if shutil.which(command) is None:
        return "nvim-jump is not installed: skip jumping."

    code, output = run_command([command, *arguments], cwd)
    if code in (2, 127):
        return "nvim-jump is not installed: skip jumping."
    if code == 1:
        return "no nvim owns this directory: anchors printed only."
    if code == 0:
        return "jumped to the first ask: ]k and [k step the rest."
    return f"nvim-jump exit {code}: {output}"


def numbered_ask_lines(asks, detail=False):
    """The numbered listing of the asks, each with the one change an accepted answer makes; a multi-line text's later
    lines sit indented under its number. detail adds the location and `[gate/class]` after the number and lists the
    question alone, as /review prints it."""
    lines = []
    for number, item in enumerate(asks, 1):
        if detail:
            ask_class = item["class"] + (f" (was {item['class_raw']})" if item.get("class_raw") else "")
            lines.append(f"{number}. {item.get('file_line') or 'no file:line'}  [{item['gate']}/{ask_class}]")
            lines += hanging_indent_lines("   ", item["question"])
        else:
            lines += hanging_indent_lines(f"{number}. ", ask_text(item))
        if item.get("change"):
            lines += hanging_indent_lines("   Proposed change: ", item["change"])
    return lines


class OutcomeRow(NamedTuple):
    """One ask's outcome row: the finding_id it was logged under, the log helper's exit code and output, and the
    stderr note for an ask logged under a new id (None otherwise)."""
    finding_id: str
    code: int
    output: str
    new_finding_id_note: str | None


def supply_finding_ask_ids(asks, session_id, logger, context, cwd=None):
    """Give each ask that is a finding the id of its ask row, as handback.supply_ask_finding_ids does."""
    # handback is imported where it is used, so code_step can read ASK_OUTCOMES and report a missing handback.py.
    import handback

    finding_asks = [item for item in asks if not handback.is_plan_impact_ask(item)]
    handback.supply_ask_finding_ids(finding_asks, session_id, logger, context, cwd)


def log_ask_outcome(logger, context, item, outcome, decided_by, cwd=None):
    """The OutcomeRow of one ask's outcome, logged with the log helper at `logger`, or None for a plan-impact ask.
    context holds the run fields the ask row and its outcome row share."""
    import handback

    if handback.is_plan_impact_ask(item):
        return None

    finding_id, new_finding_id_note = handback.ask_outcome_finding_id(item)
    code, output = run_command(["bash", str(logger), "kind=finding", f"finding_id={finding_id}",
                                *handback.ask_row_fields(context, item), f"ask_outcome={outcome}",
                                f"ask_decided_by={decided_by}"], cwd)
    return OutcomeRow(finding_id, code, output, new_finding_id_note)
