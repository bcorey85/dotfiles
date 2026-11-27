"""review_loop_round_settle.py: the booking of a coder pass on reviewer-round findings, as a mixin for `LoopRun`. The
host holds files_touched, skipped_fp, fixed, put_back_findings, round_fixes and the keep_open, drop_open,
not_put_back, mark_standing_rewords_applied, record_coder_plan_impact and findings_on_reverted_paths methods."""
from coder_report import skipped_issues
from finding_record import unseen
from review_loop_findings import PLAN_CHANGE_YES
from review_loop_ruled import prior_issue_entries

NO_CHANGE_REASON = "the coder made no change"


def folded_into(item, finding):
    """Whether `item` is `finding`, or a merged finding that holds it as a part: equal text, never a substring."""
    return any(part.text == finding.text for part in item.each_part)


class RoundSettle:
    def settle_round_repair(self, findings, result, only):
        """Books a coder pass on reviewer-round findings: files touched, adopted rewords, plan impact, skips, reverted
        findings, open and fixed findings, and the `actioned` mark of each round fix (only those in `only`).
        Returns (skipped findings, applied findings, prior-issue entries)."""
        changed = result.changed
        self.files_touched.update(changed)
        self.mark_standing_rewords_applied(changed)

        skips = skipped_issues(result.report, len(findings))
        plan_reported = PLAN_CHANGE_YES.search(result.report.strip()) is not None
        plan_held = plan_reported and self.record_coder_plan_impact(result.report, changed)

        reverted_findings = self.findings_on_reverted_paths(findings, result.reverted)
        skipped_findings, round_open_fixes = self.record_skips(findings, skips, changed, plan_held,
                                                               reverted_findings)
        round_open_fixes += [item for item in self.put_back_findings if item not in round_open_fixes]
        self.keep_open(round_open_fixes)
        self.mark_round_fixes(round_open_fixes + reverted_findings, skipped_findings, only)
        applied = self.not_put_back(item for item in findings
                                    if item not in skipped_findings and item not in reverted_findings)
        self.fixed += unseen(self.fixed, applied)
        self.drop_open([*applied, *reverted_findings])
        # A finding skipped with no coder line is one a no-change pass left alone: it reads as skipped, not fixed.
        prior_skips = {**{number: NO_CHANGE_REASON for number, item in enumerate(findings, 1)
                          if item in skipped_findings}, **skips}
        prior_entries = prior_issue_entries(findings, prior_skips, self.put_back_findings, reverted_findings)
        return skipped_findings, applied, prior_entries

    def record_skips(self, round_findings, skips, changed, plan_held, reverted_findings):
        """Sorts the round's findings the coder did not fix. Returns (skipped findings, findings still open); the
        skipped list leaves out the reverted findings. With a plan impact held, the coder's skips stay open;
        otherwise they join skipped_fp. A finding in `reverted_findings` (filed on an approval-only path that the
        loop reverted, see `REVERTED_APPROVAL_EDIT_REASON`) is filed as an approval ask, user-only unless
        `session_rules_approval_path`, or dropped as a repeat of a rejected one, and is never recorded as fixed,
        skipped_fp or open, whatever the coder reported."""
        skipped_entries = [{"item": round_findings[number - 1], "reason": line}
                           for number, line in sorted(skips.items())
                           if round_findings[number - 1] not in reverted_findings]
        round_open_fixes = []
        if plan_held:
            round_open_fixes += [entry["item"] for entry in skipped_entries]
        else:
            self.skipped_fp += skipped_entries
        skipped_findings = [entry["item"] for entry in skipped_entries]
        if changed:
            return skipped_findings, round_open_fixes

        # A put-back finding stays open through put_back_findings: it is no false positive.
        unchanged = self.not_put_back(item for item in round_findings
                                      if item not in skipped_findings and item not in reverted_findings)
        if plan_held:
            round_open_fixes += unchanged
        else:
            self.skipped_fp += [{"item": item, "reason": NO_CHANGE_REASON} for item in unchanged]
        return skipped_findings + unchanged, round_open_fixes

    def mark_round_fixes(self, round_open_fixes, skipped_findings, only=None):
        """Sets `actioned` on each fix this round's reviewers filed (only those whose finding is in `only`, when
        given): none while open or filed as an approval ask, skipped_fp, or fixed. A fix takes an item's status when it
        is the item or one of the parts the item merges."""
        for finding in self.round_fixes:
            if only is not None and finding["finding"] not in only:
                continue
            if any(folded_into(item, finding["finding"]) for item in round_open_fixes):
                finding["actioned"] = "none"
                continue

            skipped = any(folded_into(item, finding["finding"]) for item in skipped_findings)
            finding["actioned"] = "skipped_fp" if skipped else "fixed"
