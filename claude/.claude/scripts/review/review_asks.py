"""review_asks.py: the ask ids, ask outcome rows, numbered ask listing and nvim-jump anchors of a review packet,
for /review (review_fix.py).
A plan-impact ask is not a finding: it gets no id and logs no outcome row."""
import pathlib
import re
import shutil
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib", "../code")]
import handback
import handback_store
import plan_format
from ask_outcome_words import ACCEPTED, REJECTED, USER_ONLY_KEY, USER_ONLY_MARK, user_only_numbers
from script_utils import ask_text, hanging_indent_lines, one_line, run_command

MODIFIED = "modified"
ASK_OUTCOMES = (ACCEPTED, REJECTED, MODIFIED)
ACCEPT_MEANS = "make this change"
REJECT_MEANS = "leave the code as it is"
JUMP_NOTE_LIMIT = 160
# The ask field that marks an ask converted from a finding the user already accepted. Its change is that finding's
# line, so the conditional-change check skips it.
USER_RULED_KEY = "user_ruled"
# A proposed change that hangs on the answer to the ask: it starts with `If not`, `If no` (not `If no-op`), `Unless`,
# `Otherwise` or `If the user`, or it holds anywhere `if yes`, `if no,`, `if (not) confirmed/
# approved` or `if the user confirms/approves/accepts/agrees/says`. An accepted answer to it applies the branch the
# user never chose. A condition inside ordinary code, such as "Return 202 if accepted by the queue" or "Show the banner
# if the user is an admin", is not one. Nor is `If accepted, X`: it means X once accepted.
CONDITIONAL_CHANGE = re.compile(
    r"^\s*(if not|if no(?!-)|unless|otherwise|if the user)\b"
    r"|\bif yes\b|\bif no,|\bif (not )?(confirmed|approved)\b"
    r"|\bif the user (confirms|approves|accepts|agrees|says)\b",
    re.IGNORECASE)
# One path with a line or line range and nothing else: a list of locations or a bare path has no one place to jump to.
JUMP_ANCHOR = re.compile(r"^[^\s,;]+:\d+(-\d+)?$")


WRONG_COUNT = "wrong-count"
UNKNOWN_OUTCOME = "unknown-outcome"
MISSING_NOTE = "missing-note"


class OutcomeError(Exception):
    """An outcome word the grammar refuses. `problem` is WRONG_COUNT, UNKNOWN_OUTCOME or MISSING_NOTE; `number` is the
    1-based word that broke it (0 for a wrong count); `word` is that word (every word given, for a wrong count)."""

    def __init__(self, problem, number, word):
        super().__init__(f"{problem}: outcome {number} {word!r}")
        self.problem = problem
        self.number = number
        self.word = word


def parse_outcome_words(words, count, allowed, note_required):
    """(the outcome of each word, the note after `:` of each, "" when none). Raises OutcomeError for a wrong number of
    words, an outcome not in `allowed`, or an outcome in `note_required` with a blank note."""
    if len(words) != count:
        raise OutcomeError(WRONG_COUNT, 0, words)
    outcomes, notes = [], []
    for number, word in enumerate(words, 1):
        outcome, _separator, note = word.partition(":")
        if outcome not in allowed:
            raise OutcomeError(UNKNOWN_OUTCOME, number, word)
        if outcome in note_required and not note.strip():
            raise OutcomeError(MISSING_NOTE, number, word)
        outcomes.append(outcome)
        notes.append(one_line(note, None))
    return outcomes, notes


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


def is_conditional_change(text):
    """True when the proposed change text is conditional, so accepting or rejecting it as written is ambiguous."""
    return CONDITIONAL_CHANGE.search(text) is not None


def accept_reject_lines(change):
    """The lines that state a proposed change with what accepting and rejecting it do, as every ask listing shows it."""
    change_text = str(change).rstrip().rstrip(".")
    stop = "" if change_text.endswith(("?", "!")) else "."
    text = f"{change_text}{stop} Reject = {REJECT_MEANS}."
    return hanging_indent_lines(f"   Accept = {ACCEPT_MEANS}: ", text)


def user_only_refusal(asks, ruler, user_command):
    """The refusal text when a session (`ruler` is not the user) rules on an ask only the user rules, else None.
    `user_command` is the call that records the user's ruling."""
    if ruler == plan_format.USER_RULING:
        return None
    numbers = [str(number) for number in user_only_numbers(asks)]
    if not numbers:
        return None
    return (f"ask(s) {', '.join(numbers)} are user_only: only the user rules them, never the session (a fix coder "
            "edited an approval-only file). Hand them to the user, and when the user has ruled, record the user's "
            f"outcome with `--by user`: `{user_command}` with the user's outcome")


def numbered_ask_lines(asks, detail=False):
    """The numbered listing of the asks, each with the one change an accepted answer makes; a multi-line text's later
    lines sit indented under its number. detail adds the location and `[gate/class]` after the number and lists the
    question alone, as /review prints it. A `user_only` ask is marked."""
    lines = []
    for number, item in enumerate(asks, 1):
        is_user_only = bool(item.get(USER_ONLY_KEY))
        if detail:
            ask_class = item["class"] + (f" (was {item['class_raw']})" if item.get("class_raw") else "")
            user_suffix = f" {USER_ONLY_MARK}" if is_user_only else ""
            lines.append(f"{number}. {item.get('file_line') or 'no file:line'}  [{item['gate']}/{ask_class}]"
                         f"{user_suffix}")
            lines += hanging_indent_lines("   ", item["question"])
        else:
            user_prefix = f"{USER_ONLY_MARK} " if is_user_only else ""
            lines += hanging_indent_lines(f"{number}. {user_prefix}", ask_text(item))
        if item.get("change"):
            lines += accept_reject_lines(item["change"])
    return lines


class OutcomeRow(NamedTuple):
    """One ask's outcome row: the finding_id it was logged under, the log helper's exit code and output, the stderr
    note for an ask logged under a new id (None otherwise), and the command that logs the row."""
    finding_id: str
    code: int
    output: str
    new_finding_id_note: str | None
    command: list


def supply_finding_ask_ids(asks, session_id, logger, context, cwd=None, stall=None):
    """Give each ask that is a finding the id of its ask row, as handback.supply_ask_finding_ids does."""
    finding_asks = [item for item in asks if not handback.is_plan_impact_ask(item)]
    handback.supply_ask_finding_ids(finding_asks, session_id, logger, context, cwd, stall)


def log_ask_outcome(logger, context, item, outcome, decided_by, cwd=None, stall=None):
    """The OutcomeRow of one ask's outcome, logged with the log helper at `logger`, or None for a plan-impact ask.
    context holds the run fields the ask row and its outcome row share. A `stall` that an earlier call set skips the
    call: the row comes back not logged, with its command."""
    if handback.is_plan_impact_ask(item):
        return None

    finding_id, new_finding_id_note = handback.ask_outcome_finding_id(item)
    command = ["bash", str(logger), "kind=finding", f"finding_id={finding_id}",
               *handback.ask_row_fields(context, item), f"ask_outcome={outcome}", f"ask_decided_by={decided_by}"]
    result = handback.run_logger(command, cwd, stall)
    return OutcomeRow(finding_id, result.code, result.output, new_finding_id_note, command)


def rejected_ask_text(item):
    """The text a rejected ask is stored under: its file:line and question (the text before the ask's change, the part
    a later review loop compares). Review-fix and phase asks share this shape: handback.normalize_ask fills the
    question; review_loop_packet sets file_line (`path:line` or UNLOCATED)."""
    question = one_line(item["question"], None)
    # An ask with no location is stored as its question alone: a live ask's title has no `unlocated` word to match.
    if item["file_line"] == handback.UNLOCATED:
        return question
    return f"{item['file_line']} {question}"


def record_rejected_asks(session_ids, repo, asks, outcomes):
    """Records each ask answered "rejected" in the hand-back store under `repo` (the key handback_store.ruled_rows_repo
    gives), once for each of `session_ids`, so a later round of the review loop drops a repeat of it instead of
    stopping on it. A text a session already holds as rejected adds no row."""
    for item, outcome in zip(asks, outcomes, strict=True):
        if outcome != REJECTED:
            continue
        text = rejected_ask_text(item)
        for session_id in session_ids:
            handback_store.record_rejected_ask(session_id, text, repo)
