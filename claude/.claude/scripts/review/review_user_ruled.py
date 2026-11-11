"""review_user_ruled.py: the packet step of a fix run whose findings the user accepted (`launch --user-ruled`).

A finding the user accepted never lands in `skipped_fp` on the fix coder's say-so alone: each skipped entry the user
gave comes back as an ask that carries the coder's reason, and the packet stops on it like on any other ask.
"""
import handback
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
    }
    handback.normalize_ask(ask)
    return ask


def skipped_become_asks(packet):
    """Moves each skipped_fp entry the user gave (marked `given`) into packet["ask"] as an ask. Entries without
    `given` (a review round, a repair, or the held-file filter) stay in skipped_fp."""
    given = [entry for entry in packet["skipped_fp"] if entry.get("given")]
    kept = [entry for entry in packet["skipped_fp"] if not entry.get("given")]
    packet["ask"] = [*packet["ask"], *[skipped_entry_as_ask(entry) for entry in given]]
    packet["skipped_fp"] = kept
