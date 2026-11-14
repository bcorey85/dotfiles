"""review_user_ruled.py: the packet step of a fix run whose findings the user accepted (`launch --user-ruled`).

A finding the user accepted never lands in `skipped_fp` on the fix coder's say-so alone: each skipped entry the user
gave comes back as an ask that carries the coder's reason, except a plan impact a recorded ruling already settled,
and the packet stops on it like on any other ask.
"""
import os

import handback
import handback_store
from handback_store import NO_RULINGS
from review_asks import USER_RULED_KEY
from review_loop_findings import is_plan_item_text, near_title, ruled_plan_impact
from script_utils import drop_numbered, one_line

SKIP_QUESTION = "You accepted this change; the fix coder skipped it: {reason}. Apply it anyway?"


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


def leave_out_ruled_impacts(findings, user_ruled_numbers, rulings=NO_RULINGS):
    """(the findings without the plan-change findings a ruling settled, the user-ruled numbers renumbered to follow,
    the dropped findings). The fix coder would skip such a finding for want of a sign-off the ruling already gave."""
    dropped_numbers = [number for number, text in enumerate(findings, 1)
                       if settled_by_recorded_ruling(text, rulings, number in user_ruled_numbers)]
    dropped = [findings[number - 1] for number in dropped_numbers]
    kept, kept_numbers = drop_numbered(findings, dropped_numbers, user_ruled_numbers)
    return kept, kept_numbers, dropped


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
