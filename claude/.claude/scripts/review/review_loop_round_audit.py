"""review_loop_round_audit.py: the check that every fix finding a round's reviewers filed reaches a coder brief or an
ask before the next review round is built, as a mixin for `LoopRun`. The host holds iter_count, asks, round_fixes,
repair and settle_round_repair."""
import typing

from review_loop_pass_names import missed_fix_pass


class MissedFixes(typing.NamedTuple):
    """What the pass on the unsent findings produced: their prior-issue entries, the files and diffs it changed, and
    the findings it skipped and applied."""

    prior_entries: list
    changed: list
    diffs: list
    skipped: list
    applied: list


class RoundAudit:
    def init_round_audit(self):
        """Starts the per-round state: {round: texts of every finding part a coder pass of that round was briefed
        on}."""
        self.briefed_by_round = {}

    def note_briefed(self, findings):
        """Records the findings a coder pass is briefed on, under the round it runs in."""
        texts = self.briefed_by_round.setdefault(self.iter_count, set())
        for finding in findings:
            texts.update(part.text for part in finding.each_part)

    def unsent_round_fixes(self):
        """The fix entries this round's reviewers filed whose finding is in no coder brief of this round and no
        ask."""
        briefed = self.briefed_by_round.get(self.iter_count, set())
        asked = {ask.text for ask in self.asks}
        return [entry for entry in self.round_fixes
                if entry["finding"].text not in briefed and entry["finding"].text not in asked]

    def sent_round_fixes(self):
        """The findings of this round's fix entries that a coder brief of this round holds. A finding only an ask
        holds is not one: no coder was briefed on it."""
        briefed = self.briefed_by_round.get(self.iter_count, set())
        return [entry["finding"] for entry in self.round_fixes if entry["finding"].text in briefed]

    def send_missed_fixes(self):
        """One coder pass on all the fix findings of the round that no brief or ask holds. Returns a MissedFixes: the
        prior-issue entries of the findings it sent, built as the round pass's are, plus the files and diffs the pass
        changed and the findings it applied or skipped, for the caller to merge into the round's. A coder pass that
        cannot run raises the error `repair` raises, which stops the loop with a blocker."""
        unsent = self.unsent_round_fixes()
        if not unsent:
            return MissedFixes([], [], [], [], [])

        findings = [entry["finding"] for entry in unsent]
        result = self.repair(missed_fix_pass(self.iter_count), findings)
        skipped, applied, prior_entries = self.settle_round_repair(findings, result, only=findings)
        return MissedFixes(prior_entries, result.changed, result.diffs, skipped, applied)
