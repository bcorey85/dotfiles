"""review_asks.py: the ask ids, ask outcome rows, numbered ask listing and hunk-notes anchors of a review packet,
for /review (review_fix.py).
A plan-impact ask is not a finding: it gets no id and logs no outcome row."""
import pathlib
import re
import shutil
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback
import handback_store
import plan_format
from ask_outcome_words import (
    ACCEPTED,
    APPLIED,
    CRITERIA_KEY,
    HELD,
    REJECTED,
    RELAY_USAGE,
    USER_ONLY_KEY,
    USER_ONLY_MARK,
    user_only_numbers,
    user_only_reason,
)
from review_fix_names import FILED_AT_KEY
from review_fix_state import UsageError
from review_loop_findings import CHANGE_IF_LABEL_PATTERN, ask_parts
from script_utils import (
    ask_text,
    hanging_indent_lines,
    names_a_file,
    one_line,
    or_list,
    run_command,
)

MODIFIED = "modified"
ASK_OUTCOMES = (ACCEPTED, REJECTED, MODIFIED, APPLIED)
# The words a first `--by session` asks-done call takes: the ruling outcomes and `held`.
SESSION_CALL_OUTCOMES = (*ASK_OUTCOMES, HELD)
# The outcomes that carry no change of their own: each is refused on a conditional change, which only `modified`
# answers.
PLAIN_OUTCOMES_TEXT = or_list([word for word in ASK_OUTCOMES if word != MODIFIED])
ACCEPT_MEANS = "make this change"
APPLIED_MEANS = "the change is already in the tree: nothing to change"
REJECT_MEANS = "leave the code as it is"
HELD_MEANS = "a user_only ask in a session call waits for the user's `--by user` call"
NOTE_TEXT_LIMIT = 160
# The ask field that marks an ask converted from a finding the user already accepted. Its change is that finding's
# line, so the conditional-change check skips it.
USER_RULED_KEY = "user_ruled"
# A proposed change that hangs on the answer to the ask: it starts with `If not`, `If no` (not `If no-op`), `Unless`,
# `Otherwise` or `If the user`, or it holds anywhere `if yes`, `if no,`, `if (not) confirmed/
# approved` or `if the user confirms/approves/accepts/agrees/says`. An accepted answer to it applies the branch the
# user never chose. A condition inside ordinary code, such as "Return 202 if accepted by the queue" or "Show the banner
# if the user is an admin", is not one. Nor is `If accepted, X`: it means X once accepted. A `Change if <answer>:`
# label inside a change marks a second branch of an ask (`Change if yes: A. Change if no: B`): an ask with two such
# labels splits at the first, so the labels left in its change are its branches. The label also matches with a space
# before its colon (`Change if yes :`), the form `inert_change_marks` leaves in quoted text.
CONDITIONAL_CHANGE = re.compile(
    r"^\s*(if not|if no(?!-)|unless|otherwise|if the user)\b"
    r"|\bif yes\b|\bif no,|\bif (not )?(confirmed|approved)\b"
    r"|\bif the user (confirms|approves|accepts|agrees|says)\b"
    r"|" + CHANGE_IF_LABEL_PATTERN,
    re.IGNORECASE)
# One path with a line or line range and nothing else: a list of locations
# or a bare path has no one place to anchor a note.
NOTE_ANCHOR = re.compile(r"^[^\s,;]+:\d+(-\d+)?$")


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


def note_anchor_args(asks):
    """The hunk-notes arguments for the asks: `--note <question> <path:line>` for each ask whose file_line is one
    well-formed anchor. Empty when no ask has one."""
    arguments = []
    for item in asks:
        file_line = item.get("file_line") or ""
        if NOTE_ANCHOR.match(file_line):
            arguments += ["--note", one_line(item.get("question", ""), NOTE_TEXT_LIMIT), file_line]
    return arguments


def run_hunk_notes(command, asks, cwd=None):
    """Run the hunk-notes `command` once over the asks' anchors and return a line saying what happened."""
    arguments = note_anchor_args(asks)
    if not arguments:
        return "no ask names a file:line: nothing to post."
    if shutil.which(command) is None:
        return "hunk-notes is not installed: skip posting."

    code, output = run_command([command, *arguments], cwd)
    if code == 127:
        return "hunk-notes is not installed: skip posting."
    if code == 2:
        return "hunk-notes got bad arguments or hunk is missing: skip posting."
    if code == 1:
        return (
            "hunk-notes could not post (file not in a git repo, no such directory, "
            "no hunk session owns this repo, or hunk cannot show the file): "
            "anchors printed only."
        )
    if code == 0:
        # hunk-notes exits 0 even when no anchor landed on a line its diff shows, so its own
        # "(posted/total notes)" summary is the only truthful word on what was posted.
        summary = output.splitlines()[-1] if output else "no summary line"
        return f"hunk-notes: {summary}"
    return f"hunk-notes exit {code}: {output}"


def is_conditional_change(text):
    """True when the proposed change text is conditional, so accepting or rejecting it as written is ambiguous."""
    return CONDITIONAL_CHANGE.search(text) is not None


def is_unlocated_change(item):
    """True when a finding ask has no location and its change names no file, so a coder given the change alone could
    not tell what to edit."""
    if handback.is_plan_impact_ask(item):
        return False
    file_line = item.get("file_line") or ""
    if file_line and file_line != handback.UNLOCATED:
        return False
    return not names_a_file(item.get("change") or "")


# The extra steps for an ask whose change names no file.
UNLOCATED_CHANGE_ADVICE = (" (write a root or extensionless file as `./name`; when no file is known, end the run with "
                           "a stop that names the ask and asks which file and edit, keep the `To go on:` line "
                           f"last, and answer the resume with '{MODIFIED}:<change naming the file>')")


def refuse_unlocated_changes(asks, outcomes, notes, rerun_command):
    """Refuses an `accepted` outcome on a finding ask with no location whose change names no file, and a `modified`
    outcome on one whose note names no file: the coder would get the change with nothing to edit. `rerun_command`
    is the call that answers the asks again."""
    problems = []
    for number, (item, outcome, note) in enumerate(zip(asks, outcomes, notes, strict=True), 1):
        if outcome not in (ACCEPTED, MODIFIED) or not is_unlocated_change(item):
            continue
        if outcome == MODIFIED and names_a_file(note):
            continue
        if outcome == MODIFIED:
            problems.append(f"ask {number} (no file:line): the modified change names no file: "
                            f"{one_line(note, 160)}")
            continue
        change = item.get("change") or ""
        problems.append(f"ask {number} (no file:line) has a proposed change that names no file: "
                        f"{one_line(change, 160)}")
    modified_answer_refusal(problems, "the change, naming the file and the edit", rerun_command,
                            advice=UNLOCATED_CHANGE_ADVICE)


def conditional_ask_numbers(asks):
    """The 1-based numbers of the asks whose proposed change hangs on the answer. A converted ask's change is the
    skipped finding line the user already accepted; any "if" in it is not a branch for the user to pick."""
    return [number for number, item in enumerate(asks, 1)
            if not item.get(USER_RULED_KEY) and is_conditional_change(item.get("change") or "")]


def refuse_conditional_changes(asks, outcomes, rerun_command):
    """Refuses any outcome but modified on an ask whose proposed change is conditional: no other word says
    which branch the ruler chose. A modified outcome carries the ruler's own change and is never refused.
    `rerun_command` is the call that answers the asks again."""
    problems = []
    conditional = conditional_ask_numbers(asks)
    for number, (item, outcome) in enumerate(zip(asks, outcomes, strict=True), 1):
        if outcome == MODIFIED or number not in conditional:
            continue
        change = item.get("change") or ""
        problems.append(f"ask {number} ({item.get('file_line') or 'no file:line'}) has a conditional proposed "
                        f"change: {one_line(change, 160)}")
    modified_answer_refusal(problems, "the change to make, with no condition", rerun_command)


def modified_answer_refusal(problems, wanted_change, rerun_command, advice=""):
    """Raises the refusal that asks for a `modified:` answer to each problem ask; does nothing with no problems.
    `rerun_command` is the call that answers the asks again."""
    if not problems:
        return
    raise UsageError("\n".join(problems) + "\nNothing was logged. Answer each of these asks with "
                     f"'{MODIFIED}:<{wanted_change}>', quoted as one shell word{advice}, and run "
                     f"`{rerun_command}` again.")


def accept_reject_lines(change):
    """The lines that state a proposed change with what accepting and rejecting it do, as every ask listing shows it."""
    change_text = str(change).rstrip().rstrip(".")
    stop = "" if change_text.endswith(("?", "!")) else "."
    text = f"{change_text}{stop} Reject = {REJECT_MEANS}."
    return hanging_indent_lines(f"   Accept = {ACCEPT_MEANS}: ", text)


def user_only_refusal(asks, ruler, user_command, holdable=False):
    """The refusal text when a session (`ruler` is not the user) rules on an ask only the user rules, else None.
    `user_command` is the call that records the user's ruling. `holdable` names `held`, the word a first asks-done
    call gives such an ask."""
    if ruler == plan_format.USER_RULING:
        return None
    numbers = user_only_numbers(asks)
    if not numbers:
        return None
    reasons = "; ".join(f"ask {number}: {user_only_reason(asks[number - 1])}" for number in numbers)
    listed = ", ".join(str(number) for number in numbers)
    held_text = ""
    if holdable:
        held_text = (f" A session call gives `{HELD}` for each of them and an outcome for each plain ask: "
                     f"{HELD}: {HELD_MEANS}.")
    return (f"ask(s) {listed} are user_only: only the user rules them, never the session ({reasons}).{held_text}"
            f" Hand them to the user, and when the user has ruled, record "
            f"the user's outcome with `--by user`: `{user_command}` with the user's outcome. A user ruling given to "
            f"another session is recorded with `{RELAY_USAGE}` added to that call")


def ruler_of_ask(item, call_ruler):
    """Who decided one ask. A `--by user` call is the user's ruling on a user-only ask only; the session rules the
    other asks of the batch."""
    if call_ruler == plan_format.USER_RULING and item.get(USER_ONLY_KEY):
        return plan_format.USER_RULING
    return plan_format.SESSION_RULING


def stamp_filed_at(asks, now):
    """Gives each ask in `asks` with no filed time the time `now` (epoch seconds) under FILED_AT_KEY: a relayed
    ruling must come from a user turn after it. An ask that has one keeps it."""
    for item in asks:
        item.setdefault(FILED_AT_KEY, now)


ASK_MARKER = "\N{LARGE ORANGE DIAMOND}"


def ask_line_open(number):
    """What an ask line opens with: the marker emoji, then the number and a dot. Nothing parses it back."""
    return f"{ASK_MARKER} {number}."


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
            location = item.get("file_line") or "no file:line"
            lines.append(f"{ask_line_open(number)} {location}  [{item['gate']}/{ask_class}]{user_suffix}")
            lines += hanging_indent_lines("   ", item["question"])
        else:
            user_prefix = f"{USER_ONLY_MARK} " if is_user_only else ""
            lines += hanging_indent_lines(f"{ask_line_open(number)} {user_prefix}", ask_text(item))
        if item.get(CRITERIA_KEY):
            lines.append(f"   Names criteria: {', '.join(item[CRITERIA_KEY])}.")
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
    # The log knows three outcomes; an applied ask is one the ruler accepted.
    logged_outcome = ACCEPTED if outcome == APPLIED else outcome
    command = ["bash", str(logger), "kind=finding", f"finding_id={finding_id}",
               *handback.ask_row_fields(context, item), f"ask_outcome={logged_outcome}",
               f"ask_decided_by={decided_by}"]
    result = handback.run_logger(command, cwd, stall)
    return OutcomeRow(finding_id, result.code, result.output, new_finding_id_note, command)


def rejected_ask_text(item):
    """The text a rejected ask is stored under: its file:line and question (the text before the ask's change, the part
    a later review loop compares). Review-fix and phase asks share this shape: handback.normalize_ask fills the
    question; review_loop_packet sets file_line (`path:line` or UNLOCATED)."""
    question = rejected_ask_question(item)
    # An ask with no location is stored as its question alone: a live ask's title has no `unlocated` word to match.
    if item["file_line"] == handback.UNLOCATED:
        return question
    return f"{item['file_line']} {question}"


def rejected_ask_question(item):
    """The question of ask `item` on one line: what a rejection stores in its `question` field."""
    return one_line(item["question"], None)


def ask_question(ask):
    """The question of finding record `ask` on one line, which an ask is compared by. It equals the stored
    `rejected_ask_question` of the ask's item because the packet builds that question from the same `ask_parts`."""
    return one_line(ask_parts(ask.text).question, None)


def record_rejection(session_id, item, repo):
    """Records ask `item` as rejected for `session_id` in `repo`, with its text and its question field."""
    handback_store.record_rejected_ask(session_id, rejected_ask_text(item), repo, rejected_ask_question(item))


def record_rejected_asks(session_ids, repo, asks, outcomes):
    """Records each ask answered "rejected" in the hand-back store under `repo` (the key handback_store.ruled_rows_repo
    gives), once for each of `session_ids`, so a later round of the review loop drops a repeat of it instead of
    stopping on it. A text a session already holds as rejected adds no row."""
    for item, outcome in zip(asks, outcomes, strict=True):
        if outcome != REJECTED:
            continue
        for session_id in session_ids:
            record_rejection(session_id, item, repo)
