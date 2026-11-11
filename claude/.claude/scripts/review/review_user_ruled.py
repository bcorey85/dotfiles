"""review_user_ruled.py: the packet step of a fix run whose findings the user accepted (`launch --user-ruled`).

A finding the user accepted never lands in `skipped_fp` on the fix coder's say-so alone: each skipped entry the user
gave comes back as an ask that carries the coder's reason, and the packet stops on it like on any other ask.
"""
import handback
from review_asks import USER_RULED_KEY
from script_utils import one_line

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


def is_user_ruled_entry(entry, user_ruled):
    """Whether the user accepted the finding a skipped_fp entry names. `user_ruled` is the list of the texts of the
    findings the user accepted."""
    if not entry.get("given"):
        return False
    return entry["item"] in user_ruled


def skipped_become_asks(packet, user_ruled):
    """Moves each skipped_fp entry of a finding the user accepted into packet["ask"] as an ask. Entries the user did
    not accept (a review round, a repair, the held-file filter, a finding a session ruled on) stay in skipped_fp."""
    given = [entry for entry in packet["skipped_fp"] if is_user_ruled_entry(entry, user_ruled)]
    kept = [entry for entry in packet["skipped_fp"] if not is_user_ruled_entry(entry, user_ruled)]
    packet["ask"] = [*packet["ask"], *[skipped_entry_as_ask(entry) for entry in given]]
    packet["skipped_fp"] = kept


def apply_user_ruled(packet, user_ruled):
    """Strips the user-ruled mark from every ask the packet carries, then turns the skipped findings the user
    accepted into asks."""
    drop_packet_user_ruled_marks(packet)
    if user_ruled:
        skipped_become_asks(packet, user_ruled)
