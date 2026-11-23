"""review_fix_adopted.py: `decide keep` on a plan impact that a ruling adopted and the coder never applied.

The impact has no held plan impact in the hand-back: the loop stopped it as a critical blocker that says the coder did
not apply the adopted change, and listed the ruling's text in the packet's `adopted_unapplied`. A `keep` ruling is the
way out when the code already implements the plan as written."""

import handback_store
import plan_format
import review_user_ruled
from review_fix_plan_impacts import PlanImpactSource


def adopted_keep_source(decision, hand_back):
    """The PlanImpactSource `decide keep` rules on when the latest ruling on an impact of this session is `adopt` and
    the hand-back (a handback.HeldImpactHandBack) lists its text in `adopted_unapplied`, else None. The held impact
    is the adopted ruling's text, so the new `keep` row replaces the `adopt` row for
    `handback_store.latest_rows_per_text`."""
    if decision != plan_format.KEEP_DECISION or hand_back.packet is None:
        return None
    unapplied = hand_back.packet.get("adopted_unapplied", [])
    rows_repo = handback_store.ruled_rows_repo(".")
    adopted = review_user_ruled.session_rulings(rows_repo).adopted
    held = [{"text": ruling.text} for ruling in adopted if ruling.text in unapplied]
    if not held:
        return None
    return PlanImpactSource(None, held, hand_back.packet, hand_back.handed_back_at)
