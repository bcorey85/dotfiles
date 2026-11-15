"""The text a session-accepted approval ask has when it reaches the next fix run, built through the real chain."""
import sys

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_fix_asks
import review_loop_packet
import review_loop_ruled
from finding_record import parse_finding


def accepted_approval_ask_text(path, note=None, decided_by=None):
    """approval_ask_text -> the packet's ask entry -> the finding text of an accepted ask, as a fix run reads it.
    A `note` makes it a modified ruling by `decided_by`."""
    ask = parse_finding(review_loop_ruled.approval_ask_text(path))
    entry = review_loop_packet.ask_entry(ask, review_loop_ruled.CODER_GATE, None)
    return review_fix_asks.ask_finding_text(entry, note, decided_by)
