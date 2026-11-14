"""review_loop_ruled.py: what a review loop does with asks it drops and with findings the user already ruled on, as a
mixin for `LoopRun`. The host class holds asks, plan_impacts and resolved_texts."""
import coder_report
import handback_store
import plan_format
from finding_record import parse_finding
from review_loop_findings import (
    NOTE_ASK_REASON,
    REJECTED_ASK_REASON,
    REPEATED_ASK_REASON,
    near_title,
    pass_note_split,
    plan_change_items,
    repeats_a_rejected_ask,
    repeats_an_ask,
    ruled_plan_impact,
)
from review_loop_prompts import user_ruled_issue


def rejected_ask_records(session_id, repo):
    """The finding records of the asks the session rejected in `repo` (the reviewed repo's top level, the key
    asks-done writes under: the packet's own `--repo`), [] with no session id."""
    rows_repo = handback_store.ruled_rows_repo(repo)
    texts = handback_store.rejected_ask_texts(session_id, rows_repo)
    return [parse_finding(text) for text in texts]


class RuledFindings:
    def init_ruled_state(self):
        self.rejected_asks = []  # records of the asks the session rejected earlier, which a repeat never stops on
        # (ask, reason) of each pointer ask, pass note, repeated ask or repeat of a rejected ask, dropped before the
        # packet
        self.dropped_asks = []
        self.user_ruled = []  # the texts of the findings the user accepted, which a fix-first run applies
        self.user_ruled_at = ""  # when the fix run was launched, the ruling's time

    def drop_asks(self, asks, reason):
        """Files each ask not yet dropped under `reason`, for the packet's dropped asks."""
        already_dropped = [dropped for dropped, _reason in self.dropped_asks]
        self.dropped_asks += [(ask, reason) for ask in asks if ask not in already_dropped]

    def without_pass_notes(self, asks):
        """`asks` without its pass notes, which go to the dropped asks."""
        kept, notes = pass_note_split(asks)
        self.drop_asks(notes, NOTE_ASK_REASON)
        return kept

    def without_repeats(self, asks):
        """`asks` without its repeats (see `drops_repeated_ask`), which go to the dropped asks. An ask repeating an
        earlier one of `asks` is a repeat too. A plan-change item stays unless the session rejected it: the rejection
        wins, and `route_plan_items` settles the rest. An ask already on the loop's list word for word stays:
        `add_ask` keeps it once."""
        kept = []
        asks = self.without_rejected(asks)
        plan_items = plan_change_items(asks)
        for ask in asks:
            if ask in plan_items or ask in self.asks:
                kept.append(ask)
                continue
            if not self.drops_repeated_ask(ask, kept):
                kept.append(ask)
        return kept

    def without_impact_repeats(self, asks, ruling_held):
        """`asks` without the ones that repeat a plan impact on record, which go to the dropped asks.
        route_plan_items has by now recorded the review's plan impacts, so a plan-drift ask that repeats one is
        dropped before record_review logs a row for it. An ask held for a ruling, or already on the list word for
        word, stays: add_ask keeps it once."""
        kept = []
        for ask in asks:
            if ask in ruling_held or ask in self.asks:
                kept.append(ask)
                continue
            if not self.drops_repeated_ask(ask):
                kept.append(ask)
        return kept

    def without_rejected(self, items):
        """`items` without the ones that repeat an ask the session rejected, which go to the dropped asks."""
        kept = []
        for item in items:
            if repeats_a_rejected_ask(item, self.rejected_asks):
                self.drop_asks([item], REJECTED_ASK_REASON)
                continue
            kept.append(item)
        return kept

    def drops_repeated_ask(self, item, also_earlier=()):
        """Whether `item` repeats an earlier ask (or one of `also_earlier`), a plan impact on record, or a ruled
        text: the handoff's ruling or a finding the user accepted, either of which settles a plan-drift ask on its
        criterion ids. A repeat goes to the dropped asks."""
        impact_texts = [impact["text"] for impact in self.plan_impacts]
        ruled_texts = [*self.resolved_texts, *self.user_ruled]
        if not repeats_an_ask(item, [*self.asks, *also_earlier], impact_texts, ruled_texts):
            return False
        self.drop_asks([item], REPEATED_ASK_REASON)
        return True

    def record_plan_impact(self, impact):
        """Adds one plan impact ({text, gate, ac_change, cause, adopted, applied, settled}). The same text again, from a
        later round or a second reviewer, stays one. `applied` is True when the coder's edits for it are already in the
        tree. `settled` (default False) marks an impact an earlier ruling covers: it is adopted, never printed, and
        logs no deviation."""
        if any(near_title(entry["text"], impact["text"]) for entry in self.plan_impacts):
            return
        self.plan_impacts.append({"settled": False, **impact})

    def route_plan_items(self, agent, items):
        """(the items the coder fixes this round, the items held for a ruling). A plan impact that changes no
        acceptance criterion is adopted by rule and fixed like any finding; one that changes a criterion, or says
        nothing, is held for the end. An item the handoff's ruling, a carried finding or a finding the user accepted
        settles (see ruled_plan_impact) is a plain fix; a new one takes the path above."""
        to_coder, ruling_held = [], []
        for item in items:
            if ruled_plan_impact(item.text, self.resolved_texts, self.user_ruled):
                to_coder.append(item)
                continue

            ac_change = plan_format.changes_acceptance_criteria(item.text)
            self.record_plan_impact({"text": item.text, "gate": agent, "ac_change": ac_change,
                                     "cause": plan_format.PLAN_CAUSE, "adopted": not ac_change, "applied": False})
            (ruling_held if ac_change else to_coder).append(item)
        return to_coder, ruling_held

    def record_coder_plan_impact(self, report, changed):
        """A coder's PLAN-IMPACT report joins the plan impacts. Its edits stay and the loop goes on. A toolkit cause,
        or a cause that does not parse, is never adopted. `changed` holds the files the coder's edits changed. Returns
        True when the impact is held for a ruling. An impact that a ruling or a finding the user accepted settles is
        recorded as adopted and settled: it is never printed, logs no deviation, and is not held."""
        text = coder_report.plan_impact_block(report) or report.strip()
        cause = plan_format.stopping_plan_impact_cause([text], cause_required=True)
        ac_change = plan_format.changes_acceptance_criteria(text)
        settled = cause == plan_format.PLAN_CAUSE and ruled_plan_impact(text, self.resolved_texts, self.user_ruled)
        adopted = settled or (not ac_change and cause == plan_format.PLAN_CAUSE)
        self.record_plan_impact({"text": text, "gate": "coder", "ac_change": ac_change, "cause": cause,
                                 "adopted": adopted, "applied": bool(changed), "settled": settled})
        return not adopted and cause != plan_format.TOOLKIT_CAUSE

    def issue_text(self, finding):
        """The finding's text for the coder's issue list, marked when the user accepted the finding."""
        if finding.text not in self.user_ruled:
            return finding.text
        return user_ruled_issue(finding.text, self.user_ruled_at)
