"""review_user_ruled.py: the packet step of a fix run whose findings the user accepted (`launch --user-ruled`).

A finding the user accepted never lands in `skipped_fp` on the fix coder's say-so alone: each skipped entry the user
gave comes back as an ask that carries the coder's reason, except a plan impact a recorded ruling already settled,
and the packet stops on it like on any other ask.
"""
import os
from typing import NamedTuple

import handback
import handback_store
from finding_record import parse_finding
from handback_store import NO_RULINGS
from review_asks import USER_RULED_KEY
from review_loop_findings import is_plan_item_text, near_title, ruled_plan_impact
from script_utils import drop_numbered, locations_named, one_line

SKIP_QUESTION = "You accepted this change; the fix coder skipped it: {reason}. Apply it anyway?"


def reasked_findings(findings, questions, ruled_texts):
    """Finding number -> the `SKIPPED <n>:` line for each finding the user or a session ruled on (its text is in
    `ruled_texts`; a record with a path and line) that one of the coder's open `questions` names by its file:line. A
    coder that asks again about a finding already ruled on has not applied it. A finding nobody ruled on is never
    marked: a question about it is the coder's own open point."""
    reasked = {}
    for number, finding in enumerate(findings, 1):
        if finding.text not in ruled_texts:
            continue
        question = question_naming_finding(finding, questions)
        if question is None:
            continue
        quoted = one_line(question, None)
        reasked[number] = f"SKIPPED {number}: the coder re-asked it in OPEN QUESTIONS: {quoted}"
    return reasked


def question_naming_finding(finding, questions):
    """The first of `questions` that names the finding's file:line, None when none does."""
    pointer = (finding.path, finding.line)
    for question in questions:
        if pointer in locations_named(question):
            return question
    return None


def skipped_entry_as_ask(entry):
    """The ask entry for one skipped_fp entry: the coder's reason in the question, the skipped item's text as the
    proposed change, and the file:line and class the item's text names."""
    # The template supplies the only terminal mark after the reason.
    reason = one_line(entry["reason"], None).rstrip(" .!?:;")
    ask = {
        "question": SKIP_QUESTION.format(reason=reason),
        "change": one_line(entry["item"], None),
        "file_line": entry["file_line"],
        "class": entry.get("class"),
        USER_RULED_KEY: True,
    }
    handback.normalize_ask(ask)
    return ask


def drop_packet_user_ruled_marks(packet):
    """Removes the user-ruled mark from every ask the packet carries. Only skipped_become_asks may mark an ask as
    user-ruled; a mark in the packet itself would skip the conditional-change check."""
    for packet_ask in packet.get("ask", []):
        packet_ask.pop(USER_RULED_KEY, None)


def session_rulings(repo):
    """The handback_store.Rulings this session made in `repo` (its `handback_store.ruled_rows_repo` key), none with
    no session id."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    return handback_store.rulings(session_id, repo)


def settled_by_recorded_ruling(text, rulings, accepted=False):
    """Whether `text` is a plan-change finding that one of the `rulings.impacts` texts (plan impacts the user or the
    session ruled on) already settled. An `accepted` finding (one the user accepted) is settled only when it is the
    exact finding a ruling came from (its text, spaces collapsed, is in `rulings.finding_texts`) or a near title of a
    ruled impact; sharing a criterion id is not enough, since an accepted finding may ask for a different change to
    that criterion."""
    if not is_plan_item_text(text):
        return False
    if not accepted:
        return ruled_plan_impact(text, rulings.impacts)

    ruled_finding_lines = [one_line(known, None) for known in rulings.finding_texts]
    if one_line(text, None) in ruled_finding_lines:
        return True
    return any(near_title(known, text) for known in rulings.impacts)


def settled_impact_numbers(findings, accepted_numbers, rulings):
    """The 1-based numbers of the plan-change findings a recorded ruling settled. `accepted_numbers` are the findings
    the user or a session accepted."""
    return [number for number, text in enumerate(findings, 1)
            if settled_by_recorded_ruling(text, rulings, number in accepted_numbers)]


ADOPTED_MARK = "[plan change adopted by "


def adopted_issue(text, ruling):
    """A finding whose plan change a ruling adopted, marked with who ruled and when. The marker comes first, so a
    cut of a long issue never removes it."""
    return f"{ADOPTED_MARK}{ruling.owner}, ruled {ruling.ruled_at}] {text}"


def adopted_ruling_for(text, adopted, accepted=False):
    """The first of the `adopted` rulings (handback_store.AdoptedRuling) that settles the plan-change finding `text`,
    by the same match a keep ruling uses (see `settled_by_recorded_ruling`), None when none does. A finding that is
    the ruling's exact text or a near title of it matches whether or not it was accepted, so the ruling is never
    appended beside it as a second finding. The finding's title, without its `path:line [class]` lead, is compared
    to the ruling text's title too, since the lead would keep a finding that is the ruling text from reading as
    near it. The titles must be equal: a near title would join two impacts that differ only in a criterion id."""
    title = parse_finding(text).title
    for ruling in adopted:
        finding_texts = [ruling.finding_text] if ruling.finding_text else []
        one_ruling = handback_store.Rulings([ruling.text], finding_texts)
        if is_plan_item_text(text) and parse_finding(ruling.text).title == title:
            return ruling
        if settled_by_recorded_ruling(text, one_ruling, True):
            return ruling
        if not accepted and settled_by_recorded_ruling(text, one_ruling, False):
            return ruling
    return None


class LeftOut(NamedTuple):
    kept: list
    user_ruled_numbers: list
    session_ruled_numbers: list
    dropped: list
    adopted: dict  # 1-based number of each adopted finding in `kept` -> the AdoptedRuling that marked it


def ruling_key(ruling):
    """What makes two adopted rulings the same change: the impact text and the finding text."""
    return (ruling.text, ruling.finding_text)


def leave_out_ruled_impacts(findings, user_ruled_numbers, rulings=NO_RULINGS, session_ruled_numbers=()):
    """The findings without the plan-change findings a ruling that keeps the plan settled, the user-ruled and
    session-ruled numbers renumbered to follow, and the dropped findings. The fix coder would skip such a finding for
    want of a sign-off the ruling already gave.

    A finding a ruling that adopts the change settled stays, marked (see `adopted_issue`) and counted as user-ruled,
    and an adopted ruling with no finding among `findings` adds its text as a last finding."""
    accepted_numbers = [*user_ruled_numbers, *session_ruled_numbers]
    adopted_for = {number: adopted_ruling_for(text, rulings.adopted, number in accepted_numbers)
                   for number, text in enumerate(findings, 1)}
    adopted_numbers = [number for number, ruling in adopted_for.items() if ruling is not None]
    kept_only_numbers = settled_impact_numbers(findings, accepted_numbers, rulings)
    dropped_numbers = [number for number in kept_only_numbers if number not in adopted_numbers]
    dropped = [findings[number - 1] for number in dropped_numbers]

    marked = [adopted_issue(text, adopted_for[number]) if number in adopted_numbers else text
              for number, text in enumerate(findings, 1)]
    kept, kept_user_numbers = drop_numbered(marked, dropped_numbers, [*user_ruled_numbers, *adopted_numbers])
    _, kept_session_numbers = drop_numbered(marked, dropped_numbers, session_ruled_numbers)

    _, kept_adopted_numbers = drop_numbered(marked, dropped_numbers, adopted_numbers)
    kept_adopted = dict(zip(kept_adopted_numbers, [adopted_for[number] for number in adopted_numbers], strict=True))

    handled_keys = {ruling_key(ruling) for ruling in kept_adopted.values()}
    for ruling in rulings.adopted:
        if ruling_key(ruling) in handled_keys:
            continue
        kept.append(adopted_issue(ruling.text, ruling))
        kept_user_numbers.append(len(kept))
        kept_adopted[len(kept)] = ruling
    return LeftOut(kept, sorted(set(kept_user_numbers)), kept_session_numbers, dropped, kept_adopted)


def is_user_ruled_entry(entry, user_ruled, rulings=NO_RULINGS):
    """Whether the user accepted the finding a skipped_fp entry names, and no ruling settled it as a plan impact.
    `user_ruled` is the list of the texts of the findings the user accepted."""
    if not entry.get("given"):
        return False
    if entry["item"] not in user_ruled:
        return False
    return not settled_by_recorded_ruling(entry["item"], rulings, accepted=True)


def skipped_become_asks(packet, user_ruled, rulings=NO_RULINGS):
    """Moves each skipped_fp entry of a finding the user accepted into packet["ask"] as an ask. Entries the user did
    not accept (a review round, a repair, the held-file filter, a finding a session ruled on) and a plan impact a
    ruling settled stay in skipped_fp."""
    is_given = [is_user_ruled_entry(entry, user_ruled, rulings) for entry in packet["skipped_fp"]]
    given = [entry for entry, flag in zip(packet["skipped_fp"], is_given, strict=True) if flag]
    kept = [entry for entry, flag in zip(packet["skipped_fp"], is_given, strict=True) if not flag]
    packet["ask"] = [*packet["ask"], *[skipped_entry_as_ask(entry) for entry in given]]
    packet["skipped_fp"] = kept


def apply_user_ruled(packet, user_ruled, repo):
    """Strips the user-ruled mark from every ask the packet carries, then turns the skipped findings the user
    accepted into asks, except the plan impacts a ruling settled in `repo`, the reviewed repo."""
    drop_packet_user_ruled_marks(packet)
    if not user_ruled:
        return
    skipped_become_asks(packet, user_ruled, session_rulings(repo))
