"""The review loop's reading of reviewer text: the Fix/Ask/Plan impact/Nit sections of a review as finding records,
the merge of findings that name the same code, and the splits that drop or reroute findings (pass notes, pointer
asks, repeats, absent files, ruled plan lines)."""

import pathlib
import re
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback
import plan_format
import script_utils
from finding_record import FINDING_CLASS_TAG, combine, parse_finding
from plan_format import PLAN_CHANGE_MARK
from reply_json import last_json_object
from source_text import indent_of

UNLOCATED = handback.UNLOCATED

PLAN_CHANGE_YES = re.compile(r"plan[-_ ]?impact:\s*yes\s*$", re.I | re.M)
# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`. A reviewer also
# names the condition: `Change if accepted:`, `Change if not accepted:`, `Change if yes:`, `Change if moved:` and so
# on, with up to three words and optional markup around them.
CHANGE_IF_CONDITION = r"\s+if\s+[`*_]*\w+(?:\s+\w+){0,2}[`*_]*"
ASK_CHANGE_MARK = re.compile(rf"\bchange(?P<condition>{CHANGE_IF_CONDITION})?:", re.I)
# The same mark with its condition required: the pattern text of a `Change if <answer>:` label, or of the label after
# `inert_change_marks` put a space before its colon.
CHANGE_IF_LABEL_PATTERN = rf"\bchange{CHANGE_IF_CONDITION}\s?:"

# An ask that names another ask in place of a question: "The open ask about pinning the window still stands."
ASK_POINTER = re.compile(r"\b(?:the|that|this|my)\s+(?:open|earlier|same|previous|prior|above|first|existing|standing)"
                         r"\s+ask\b|\bask\s+#?\d+\b", re.I)
ITEM_MARKER = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
ITEM_MARKER_STRIP = re.compile(r"^\s*(?:[-*]+|\d+[.)])\s+")
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)
# The words that state a section holds nothing: "None", "None new", or "No new findings" and its forms.
NONE_WORDS = (r"(?:none(?:\s+(?:new|further|other|more|remaining))?|n/a|omitted|empty"
              r"|no(?:\s+(?:new|further|other|more|remaining))?\s+(?:findings?|issues?|asks?|nits?|concerns?|problems?)"
              r"(?:\s+(?:found|remain|to\s+report))?)")
# A bare none marker inside a section, as in "- None." A line that goes on past the word is finding text.
NONE_LINE = re.compile(r"[\[(*_`]*" + NONE_WORDS + r"[\])*_`]*[.!]?", re.I)
# A lead-in sentence about none before a section's first item, as in "None of the three queries filters by tenant:".
NONE_LEAD_IN = re.compile(r"\[?(none|n/a|omitted|empty)[^\]]*\]?\.?", re.I)
# A section's opening none line: a none word that ends its sentence, as in "None." or "None. What I checked:".
NONE_OPENING = re.compile(r"[\[(*_`]*" + NONE_WORDS + r"[\])*_`]*"
                          r"(?:[.:;,!]|\s+[\N{EM DASH}\N{EN DASH}-]|$)", re.I)
# A finding's head: its file:line first, after an optional [blocker] tag and bold markup.
FINDING_HEAD = re.compile(rf"(?:{script_utils.BLOCKER_TAG_PATTERN}\s*)?[*_]*" + script_utils.PATH_LINE.pattern,
                          re.I)


class AskParts(NamedTuple):
    """An ask's text split at its change mark (see `ask_parts`): the question, and the edit an accepted answer makes."""
    question: str
    change: str


def opens_with_plain_mark_then_condition(text, change_marks):
    """True when an ask's first change mark is plain (`change:`), follows the ask's question (`Q? change: A. Change if
    no: B.`), and a later mark carries a condition. The ask proposes A and B for different answers, so its change keeps
    both: the conditional-change check then refuses `accepted` and `applied` on it, and only `modified:<change>`
    answers it. A `change:` inside the question's own words ("Should the default change: 10 or 20?") is no mark."""
    first_mark = change_marks[0]
    if first_mark.group("condition"):
        return False
    if not any(mark.group("condition") for mark in change_marks[1:]):
        return False
    before_first_mark = text[:first_mark.start()].rstrip(" —-")
    return before_first_mark.endswith("?")


def ask_parts(text):
    """The AskParts of an ask's text. The text before the last `change:` marker is the question; the text after it is
    the edit. An ask with no marker carries its own recommended edit, so its whole text is both. An ask that opens
    with its marker asks its change, and one that ends on an empty marker carries its edit in its question. An ask
    with two or more `Change if <answer>:` marks has a branch for each answer (`Change if yes: A. Change if no: B`):
    its question ends at the first of them and its change keeps every branch, so that the conditional-change check
    refuses it. An ask whose question ends in `?` and then a plain `change:` and a later mark carries a condition
    splits at the plain one, so its change keeps the conditional branch and the same check refuses it. A plain
    `change:` inside the question's words never counts as a branch."""
    change_marks = list(ASK_CHANGE_MARK.finditer(text))
    if not change_marks:
        return AskParts(text, text)

    split_mark = change_marks[-1]
    conditional_marks = [mark for mark in change_marks if mark.group("condition")]
    if len(conditional_marks) > 1:
        split_mark = conditional_marks[0]
    if opens_with_plain_mark_then_condition(text, change_marks):
        split_mark = change_marks[0]
    after_mark = text[split_mark.end():].strip()
    before_mark = text[:split_mark.start()].rstrip(" —-")
    return AskParts(before_mark or after_mark, after_mark or before_mark)


def inert_change_marks(text):
    """`text` with each `change:` marker made unreadable to `ask_parts` (a space goes before its colon), so text that
    an ask quotes cannot move the ask's question/change split."""
    return ASK_CHANGE_MARK.sub(lambda mark: f"{mark.group(0)[:-1]} :", text)


def section(text, name):
    # The section body keeps the indent of its first line: review_section_findings compares marker indents.
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", text, re.S | re.M | re.I)
    if not match:
        return None
    return re.sub(r"\A(?:[ \t]*\n)+", "", match.group(1)).rstrip()


def states_an_ask(text):
    """Whether item text `text` proposes a change, asks a question, names a class or opens a plan change: what
    separates an ask from a reviewer's note. Only a question that ends the text asks: a `?` followed by an answer
    ("Is X bounded? Yes.") is a note."""
    ends_in_question = text.rstrip(" \t`*_\"')").endswith("?")
    return bool(ASK_CHANGE_MARK.search(text) or ends_in_question or FINDING_CLASS_TAG.search(text)
                or PLAN_CHANGE_MARK.match(text))


def is_bare_finding_head(line, is_ask_section=False):
    """A line that opens an unbulleted item: a bare file:line, or in an Ask-type section a plan-impact line."""
    if ITEM_MARKER.match(line):
        return False
    if FINDING_HEAD.match(line.strip()):
        return True
    return is_ask_section and bool(PLAN_CHANGE_MARK.match(line.strip()))


def item_start_lines(lines, is_ask_section=False):
    """The indexes of the section lines that start an item. A finding written as a paragraph opens with a bare
    file:line, and the bullets under it are its points: when the section opens with one (in an Ask-type section, also a
    `PLAN-IMPACT:` line), each such line at its indent starts an item. Otherwise a bullet or numbered marker at the
    first marker's indent starts one. A marker indented deeper is a sub-bullet, and it and any other line, after a
    blank line too, continue the item before it.
    A line at the item indent that ends in a colon, after an item or as an Ask section's first line, leads in a list
    of the reviewer's notes ("The other claims check out:"): the markers under it continue the item too, until one opens
    with a file:line or a plain line at the item indent closes the list. In an Ask-type section, an unbulleted
    `PLAN-IMPACT:` line at the item indent starts an item and closes a notes list."""
    first_line = next(line for line in lines if line.strip())
    if is_bare_finding_head(first_line, is_ask_section):
        return {index for index, line in enumerate(lines)
                if is_bare_finding_head(line, is_ask_section) and indent_of(line) <= indent_of(first_line)}

    marker_indents = [indent_of(line) for line in lines if ITEM_MARKER.match(line)]
    item_indent = marker_indents[0] if marker_indents else 0
    starts = set()
    in_notes_list = False
    opens_section = is_ask_section
    for index, line in enumerate(lines):
        if not line.strip() or indent_of(line) > item_indent:
            continue
        if not ITEM_MARKER.match(line):
            if is_ask_section and indent_of(line) == item_indent and PLAN_CHANGE_MARK.match(line.strip()):
                starts.add(index)
                opens_section = False
                in_notes_list = False
                continue
            in_notes_list = (bool(starts) or opens_section) and line.rstrip().endswith(":")
            opens_section = False
            continue
        opens_section = False

        item_text = ITEM_MARKER_STRIP.sub("", line).strip()
        # Only the Ask section's notes list holds bullets that state asks; a Fix or Nit list holds just file:line items.
        states_ask = is_ask_section and states_an_ask(item_text)
        if in_notes_list and not FINDING_HEAD.match(item_text) and not states_ask:
            continue
        starts.add(index)
        in_notes_list = False
    return starts


def is_bare_lead_in(lines, index, starts):
    """True for a line that is no item and ends in `:`, with an item starting on the next non-blank line, such as
    "Two questions for the user:". It carries no ask, so an Ask section leaves it out."""
    if index in starts or not lines[index].rstrip().endswith(":"):
        return False
    following = [number for number in range(index + 1, len(lines)) if lines[number].strip()]
    return bool(following) and following[0] in starts


def review_section_findings(block, is_ask_section=False):
    if not block:
        return []
    lines = block.splitlines()

    # A section that opens with a none line holds no finding: the lines after it are the reviewer's notes, such as
    # what it checked or why it flagged nothing.
    first_text = ITEM_MARKER_STRIP.sub("", next(line for line in lines if line.strip())).strip()
    if NONE_OPENING.match(first_text):
        return []

    starts = item_start_lines(lines, is_ask_section)
    found = []
    for index, line in enumerate(lines):
        stripped = ITEM_MARKER_STRIP.sub("", line).strip()
        if not stripped:
            continue
        if NONE_LINE.fullmatch(stripped):
            continue
        if not found and index not in starts and NONE_LEAD_IN.fullmatch(stripped):
            continue
        if ASSESSMENT_LINE.match(stripped):
            continue
        if is_ask_section and is_bare_lead_in(lines, index, starts):
            continue
        if index in starts or not found:
            found.append(stripped)
            continue
        found[-1] = f"{found[-1]} {stripped}"
    return found


TAGGED_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+`?(fix|ask|nit)`?\s*:\s*(.+)$", re.I)


BOLD_OPENING = re.compile(r"^\s*(?:(?:[-*]|\d+[.)])\s+)?(\*\*|__).+?\1")
BOLD_REPORT_FIELD = re.compile(r"^\s*(\*\*|__)[^*_]+\1\s*:")
STRAY_DISPOSITION_TAG = re.compile(r"`(?:fix|ask|nit)`|\((?:fix|ask|nit)\)|\*\*(?:fix|ask|nit)\*\*", re.I)


def opens_with_bold_head(line):
    """True for a line that opens with a bold run, other than a report header field like `**Scope**: value`."""
    return bool(BOLD_OPENING.match(line)) and not BOLD_REPORT_FIELD.match(line)


def tagged_bullets_leave_items_out(lines):
    """True when the text holds an item the tagged-bullet parse would drop or mangle: a tagged bullet nested under
    another item, a bold-head item, an untagged top-level item that names a file:line, or a stray disposition tag."""
    list_indents = [indent_of(line) for line in lines if ITEM_MARKER.match(line)]
    top_indent = min(list_indents, default=0)
    for line in lines:
        tagged = TAGGED_BULLET.match(line)
        if tagged and indent_of(line) > top_indent:
            return True
        if tagged:
            continue
        if opens_with_bold_head(line) or STRAY_DISPOSITION_TAG.search(line):
            return True
        top_level_item = ITEM_MARKER.match(line) and indent_of(line) == top_indent
        if top_level_item and script_utils.PATH_LINE.search(line):
            return True
    return False


def parse_tagged_bullets(text):
    """Reviewers that tag each bullet with its disposition (the test reviewer) instead of using Fix/Ask/Nit sections.
    Returns None, so the disposition call reads the text, unless the tagged bullets account for every item: a tagged
    bullet nested under another item, a bold-head item, an untagged top-level item naming a file:line, or a stray
    disposition tag each mean an item the bullets would drop."""
    lines = text.splitlines()
    if tagged_bullets_leave_items_out(lines):
        return None
    found = {"fix": [], "ask": [], "nit": []}
    for line in lines:
        match = TAGGED_BULLET.match(line)
        if match:
            found[match.group(1).lower()].append(match.group(2).strip())
    if not any(found.values()):
        return None
    return {**found, "assessment": ""}


def parse_review_texts(text):
    fix, ask, nit = section(text, "Fix"), section(text, "Ask"), section(text, "Nit")
    impact = section(text, "Plan impact")
    if fix is None and ask is None and nit is None and impact is None:
        return parse_tagged_bullets(text)
    assessment = re.search(r"Overall Assessment\W*\s*:?\W*\s*([A-Z][A-Z ]+[A-Z])", text)
    # A plan-impact line is taken in as an ask: it is never auto-fixed and the loop scans its prefix.
    asks = review_section_findings(ask, is_ask_section=True) + review_section_findings(impact, is_ask_section=True)
    return {"fix": review_section_findings(fix), "ask": asks,
            "nit": review_section_findings(nit),
            "assessment": assessment.group(1).strip() if assessment else ""}


def finding_records(review_texts):
    """The review with each finding's text parsed into a record."""
    return {**review_texts, **{disposition: [parse_finding(item) for item in review_texts[disposition]]
                               for disposition in ("fix", "ask", "nit")}}


def parse_review(text):
    """The review's {fix, ask, nit: [finding records], assessment}, or None when the text has no findings layout."""
    review_texts = parse_review_texts(text)
    if review_texts is None:
        return None
    return finding_records(review_texts)


class ReplyShapeError(ValueError):
    """A model reply that holds no usable object after its one retry."""


# How much of the first unusable reply's error the retry note quotes.
RETRY_ERROR_CHARS = 200


def reply_with_one_retry(claude_call, role, prompt, repo, out, keys, shape, recover=None, problem=None, **options):
    """The parsed JSON object of a model reply that holds any of `keys`. A reply with none is read by `recover`, when
    given. An object that `problem`, when given, returns a problem string for is rejected, and that string goes into
    the retry note and the error. A miss is retried once under "<role>-retry", so the retry has its own row in
    calls.jsonl; a second miss raises ReplyShapeError."""
    def parsed_reply(reply):
        """(object, error): the object is None when the reply is rejected, and the error says why."""
        parsed = last_json_object(reply, keys)
        if parsed is None and recover:
            parsed = recover(reply)
        if parsed is None:
            return None, f"the {role} reply holds no {shape} object: {reply!r}"
        rejection = problem(parsed) if problem else None
        if rejection:
            return None, f"the {role} reply's object fails its check: {rejection}: {reply!r}"
        return parsed, None

    reply = claude_call(role, prompt, repo, out, **options)
    parsed, error = parsed_reply(reply)
    if parsed is not None:
        return parsed

    retry_note = f"A previous reply to this prompt could not be used: {error[:RETRY_ERROR_CHARS]}"
    retry_prompt = prompt + f"\n\n{retry_note}\nReply with the JSON object only."
    reply = claude_call(f"{role}-retry", retry_prompt, repo, out, **options)
    parsed, error = parsed_reply(reply)
    if parsed is None:
        raise ReplyShapeError(error)
    return parsed


REFILE_SIMILARITY = 0.8


def merge_findings(findings):
    """One list for the coder: a finding that names the same file and a shared identifier as an earlier one is
    folded into it."""
    merged = []
    for finding in findings:
        home = next((index for index, kept in enumerate(merged)
                     if kept.path == finding.path and finding.identifiers & kept.identifiers and finding.path), None)
        if home is None:
            merged.append(finding)
        else:
            merged[home] = combine([*merged[home].each_part, finding])
    return merged


def near_title(title, other_title):
    """Whether two finding titles are the same or near."""
    return script_utils.text_similarity(title, other_title) >= REFILE_SIMILARITY


def same_finding(finding, other):
    """Whether two findings in the same file name the same issue: a near title when both have one, else the same
    line."""
    if finding.path != other.path:
        return False
    if finding.title and other.title:
        return near_title(other.title, finding.title)
    return finding.line == other.line


def matches_any_finding(item, findings):
    """Whether `item` is the same finding as one of `findings`."""
    return any(same_finding(item, other) for other in findings)


def names_absent_file(repo, tree_paths, finding):
    """True when the finding's file:line names a path that is not on disk and matches no path git lists. A bare
    path (no line part) never does: it may name a file the finding asks for. An approximate `~` line still does."""
    path = finding.path
    if not path or (pathlib.Path(repo) / path).exists():
        return False
    if finding.bare:
        return False
    return not any(script_utils.path_has_tail(known, path) for known in tree_paths)


def plan_change_items(items):
    """The items that say the fix would change the approved plan."""
    return [item for item in items if PLAN_CHANGE_MARK.match(item.text)]


def points_back_to_an_ask(ask):
    """Whether ask record `ask` only points back to another ask: it names one, asks no question and proposes no change
    of its own."""
    return bool(ASK_POINTER.search(ask.text)) and "?" not in ask.text and not ASK_CHANGE_MARK.search(ask.text)


def pointer_ask_split(asks, open_asks):
    """(`asks` without each ask that only points back to another ask, those pointer asks). A pointer ask leaves only
    when another ask is there to point to: one of `asks` that is not a pointer, or one of `open_asks`, the asks of
    earlier rounds."""
    pointer_asks = [ask for ask in asks if points_back_to_an_ask(ask)]
    has_a_target = len(pointer_asks) < len(asks) or bool(open_asks)
    if not has_a_target:
        return asks, []
    return [ask for ask in asks if ask not in pointer_asks], pointer_asks


POINTER_ASK_REASON = "ask only points back to another ask"
NOTE_ASK_REASON = "item proposes no change and asks no question, so it is a note and no ask"
REPEATED_ASK_REASON = "ask repeats an earlier ask or a plan impact already on record"
REVERTED_APPROVAL_EDIT_REASON = "the fix coder's edit to an approval-only file was reverted"
# Filled with `standing_rulings.ruling_label(ruling)`: who ruled and when.
KEPT_OWNER_LINE_EDIT_REASON = ("no approval ask is needed for an owner-line edit kept under the standing ruling by "
                               "{ruling}")


def is_pass_note(ask):
    """Whether ask record `ask` is a reviewer's note rather than an ask: it proposes no change, asks no question, names
    no class and is no plan-change item or pointer to another ask."""
    return not (states_an_ask(ask.text) or points_back_to_an_ask(ask))


def pass_note_split(asks):
    """(`asks` without its pass notes, those notes). A note rides in the packet's dropped asks, so it is seen."""
    notes = [ask for ask in asks if is_pass_note(ask)]
    return [ask for ask in asks if ask not in notes], notes


REJECTED_ASK_REASON = "finding repeats an ask the session already rejected"


def repeats_a_rejected_ask(ask, rejected_asks):
    """Whether ask record `ask` raises again an ask in `rejected_asks` (records of asks the session rejected): the same
    file and a near title, wherever the line, since a reviewer rewords a repeat. The title is the ask's question alone:
    asks-done stores the file:line and the question, the text before the ask's change; the title is the question's."""
    question = ask_parts(ask.text).question
    question_title = parse_finding(question).title
    return any(ask.path == rejected.path and near_title(question_title, rejected.title) for rejected in rejected_asks)


def repeats_an_ask(ask, earlier_asks, impact_texts, ruled_texts=()):
    """Whether ask record `ask` repeats an ask in `earlier_asks` (the same file and the same claim, wherever the
    line), or is a plan-drift ask on a criterion that a text in `impact_texts` or `ruled_texts` also names."""
    if any(ask.path == earlier.path and ask.title == earlier.title for earlier in earlier_asks):
        return True
    if ask.finding_class != handback.PLAN_DRIFT_CLASS:
        return False

    criteria_ids = plan_item_criteria_ids(ask.text)
    return criteria_covered(criteria_ids, [*impact_texts, *ruled_texts])


def is_plan_item_text(text):
    """Whether `text` is a plan-change item: a plan impact or a plan-drift finding. A text that only names a
    criterion on an `acceptance_criteria:` line, such as a test-gap finding, is no plan item."""
    return bool(PLAN_CHANGE_MARK.match(text)
                or parse_finding(text).finding_class == handback.PLAN_DRIFT_CLASS)


def plan_item_criteria_ids(text):
    """The criterion ids a plan-change `text` names: those on its `acceptance_criteria:` lines when it opens with the
    plan-impact mark, else every id in it."""
    return plan_format.criteria_ids(text, answers_only=bool(PLAN_CHANGE_MARK.match(text)))


def ruled_plan_impact(text, ruling_texts, accepted_texts=()):
    """Whether a plan-change `text` (a plan impact or a plan-drift finding) is one a ruling, the user or a session
    already settled. A near title of a text in `ruling_texts` or `accepted_texts` (the findings the user or a session
    ruled on) settles it. Every id it names (see `plan_item_criteria_ids`) named by a plan item in `ruling_texts`
    settles it too. An accepted finding settles no id by itself, except a re-filed plan-drift finding (see
    `refiles_accepted_drift`)."""
    if any(near_title(known, text) for known in [*ruling_texts, *accepted_texts]):
        return True

    if any(refiles_accepted_drift(text, known) for known in accepted_texts):
        return True

    criteria_ids = plan_item_criteria_ids(text)
    return criteria_covered(criteria_ids, ruling_texts)


def refiles_accepted_drift(text, accepted):
    """Whether the plan-drift finding `text` is the finding `accepted` again in other words: the same first
    file:line and the same, non-empty, criterion ids. The text of an accepted ask is much shorter than the
    reviewer's finding, so a near title cannot match them."""
    found = parse_finding(text)
    known = parse_finding(accepted)
    if found.finding_class != handback.PLAN_DRIFT_CLASS:
        return False
    if known.finding_class != handback.PLAN_DRIFT_CLASS:
        return False
    if not found.path or (found.path, found.line) != (known.path, known.line):
        return False

    text_ids = plan_format.criteria_ids(text)
    return bool(text_ids) and text_ids == plan_format.criteria_ids(accepted)


def criteria_covered(ids, plan_texts):
    """Whether every criterion id in `ids` is named by the plan items among `plan_texts`. A plan item names the ids
    on its `acceptance_criteria:` lines; a plan-drift finding with no such line names every id in it, and a plan
    impact with none names no id. A text that is no plan item, such as a test-gap finding, names none. No ids are
    never covered."""
    if not ids:
        return False

    covered = set()
    for text in plan_texts:
        if is_plan_item_text(text):
            covered |= plan_item_criteria_ids(text)
    return ids <= covered


def absent_file_split(repo, tree_paths, review):
    """(the review without its findings on a file neither on disk nor in git, those findings). A plan-change ask
    stays: it is about the plan, not the file."""
    kept, absent = {}, []
    for disposition in ("fix", "ask", "nit"):
        kept[disposition] = []
        for item in review[disposition]:
            if names_absent_file(repo, tree_paths, item) and not PLAN_CHANGE_MARK.match(item.text):
                absent.append(item)
            else:
                kept[disposition].append(item)
    return {**review, **kept}, absent


RULING_HEADINGS = (plan_format.DEVIATIONS_HEADING, "Constraints")
RULED_PLAN_NOTE = " — a recorded plan ruling covers this line; the fix would undo it"


def ruled_plan_line(plan_lines, line_number):
    """True when the plan line sits under a ruling heading, or holds a backticked value a ruling line holds."""
    ruling_indexes = [index for heading in RULING_HEADINGS
                      for index in script_utils.heading_section_indexes(plan_lines, heading)]
    target_index = line_number - 1
    if target_index in ruling_indexes:
        return True
    if not 0 <= target_index < len(plan_lines):
        return False

    ruled_values = {value for index in ruling_indexes for value in re.findall(r"`([^`]+)`", plan_lines[index])}
    target_text = plan_lines[target_index]
    return any(value in target_text for value in ruled_values)


def ruled_plan_split(repo, plan, fixes):
    """(the fixes that stay fixes, the fixes that target a plan line a recorded ruling covers, turned into asks)."""
    plan_path = pathlib.Path(repo) / plan
    if not plan or not plan_path.is_file():
        return fixes, []

    plan_lines = plan_path.read_text().splitlines()
    kept, ruled = [], []
    for item in fixes:
        if item.path == plan and ruled_plan_line(plan_lines, item.line):
            ruled.append(parse_finding(item.text + RULED_PLAN_NOTE))
        else:
            kept.append(item)
    return kept, ruled
