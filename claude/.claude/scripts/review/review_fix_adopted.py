"""review_fix_adopted.py: `decide keep` on a plan impact that a ruling adopted and the coder never applied.

The impact has no held plan impact in the hand-back: the loop stopped it as a critical blocker that says the coder did
not apply the adopted change, and listed the ruling's text in the packet's `adopted_unapplied`. A `keep` ruling is the
way out when the code already implements the plan as written."""

import handback_store
import plan_format
import review_user_ruled
from review_fix_plan_impacts import PlanImpactSource

ADOPTED_KEEP_LINE = ("The plan stays as written. The hand-back stopped on an adopted change the coder never "
                     "applied: rerun your review loop (`/code resume`) so the keep ruling settles it.")


def adopted_row_impacts(held):
    """The (ruling text, finding text) pairs `decide keep` writes one row for, from the held impacts of
    adopted_keep_source. A held impact with no finding text gives one pair with None. `write_ruling_entry` writes one
    row per pair, so each replaces its own row for `handback_store.latest_rows_per_text`; a source without
    `row_per_text` passes no pairs and gets the one joined row."""
    return [(impact["text"], finding_text) for impact in held for finding_text in impact["finding_texts"] or [None]]


def adopted_keep_source(decision, hand_back):
    """The PlanImpactSource `decide keep` rules on when the latest ruling on an impact of this session is `adopt` and
    the hand-back (a handback.HeldImpactHandBack) lists its text in `adopted_unapplied`, else None. The held impact
    is each distinct adopted ruling text, with the `finding_texts` of its adopt rows; `decide keep` writes one `keep`
    row per text and finding text, so each replaces its `adopt` row for `handback_store.latest_rows_per_text` and
    keeps the finding text a later round's re-raised finding is settled by."""
    if decision != plan_format.KEEP_DECISION or hand_back.packet is None:
        return None
    unapplied = hand_back.packet.get("adopted_unapplied", [])
    rows_repo = handback_store.ruled_rows_repo(".")
    adopted = review_user_ruled.session_rulings(rows_repo).adopted
    finding_texts_by_text = {}
    for ruling in adopted:
        if ruling.text not in unapplied:
            continue
        finding_texts = finding_texts_by_text.setdefault(ruling.text, [])
        if ruling.finding_text and ruling.finding_text not in finding_texts:
            finding_texts.append(ruling.finding_text)
    held = [{"text": text, "finding_texts": finding_texts} for text, finding_texts in finding_texts_by_text.items()]
    if not held:
        return None
    return PlanImpactSource(None, held, hand_back.packet, hand_back.handed_back_at, row_per_text=True)
