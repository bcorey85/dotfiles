"""review_fix_adopted.py: `decide keep` on a plan impact that a ruling adopted and the coder never applied.

The impact has no held plan impact in the hand-back: the loop stopped it as a critical blocker that says the coder did
not apply the adopted change. A `keep` ruling is the way out when the code already implements the plan as written."""

import os

import handback
import handback_store
import plan_format
import review_loop_ruled
import review_user_ruled
from review_fix_plan_impacts import PlanImpactSource


def blocker_lines(packet):
    """The text of each blocker of the hand-back `packet`."""
    return [handback.item_text(item, "finding", "file_line") for item in packet["blockers"]]


def carries_not_applied_blocker(ruling, blockers):
    """True when one of `blockers` is the not-applied blocker of the adopted `ruling` (see
    `review_loop_ruled.not_applied_blockers`)."""
    for text in (ruling.text, ruling.finding_text):
        if not text:
            continue
        marked = review_user_ruled.adopted_issue(text, ruling)
        if any(line in blockers for line in review_loop_ruled.not_applied_blockers(marked)):
            return True
    return False


def adopted_keep_source(decision, hand_back):
    """The PlanImpactSource `decide keep` rules on when the latest ruling on an impact of this session is `adopt` and
    `hand_back` (a handback.HeldImpactHandBack) carries its not-applied blocker, else None. The held impact is the
    adopted ruling's text, so the new `keep` row replaces the `adopt` row for `handback_store.latest_rows_per_text`."""
    if decision != plan_format.KEEP_DECISION or hand_back.packet is None:
        return None
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    repo = handback_store.ruled_rows_repo(".")
    if not session_id or not repo:
        return None
    blockers = blocker_lines(hand_back.packet)
    adopted = handback_store.rulings(session_id, repo).adopted
    held = [{"text": ruling.text} for ruling in adopted if carries_not_applied_blocker(ruling, blockers)]
    if not held:
        return None
    return PlanImpactSource(None, held, hand_back.packet, hand_back.handed_back_at)
