"""review_loop_ruled.py: what a review loop does with asks it drops, with findings the user already ruled on, and with
a coder's edit to an approval-only file (it files an ask), as a mixin for `LoopRun`. The host class holds asks,
plan_impacts, resolved_texts, repo and plan (the plan's path in repo, or ""), and provides `add_ask`."""
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import coder_report
import handback_store
import plan_format
import review_loop_ruled_out
import script_utils
import standing_rulings
from approval_asks_store import approval_change, read_approval_paths, write_approval_paths
from finding_record import parse_finding
from format_files import PROMPT_MARKDOWN_NAMES
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
from review_loop_held import held_path_in_repo, names_held_file
from review_loop_packet import located
from review_loop_prompts import user_ruled_issue
from ruled_change_text import is_no_code_finding, ruled_note
from source_paths import is_doc_path

# The fix coder's agent name: the gate of its plan impacts and of its approval asks.
CODER_GATE = "coder"


def approval_only_paths(changed):
    """The paths in `changed` whose basename is one of `PROMPT_MARKDOWN_NAMES` (CLAUDE.md, CLAUDE.local.md,
    AGENTS.md). A coder never changes these without the user's approval, so each edit becomes an ask."""
    return [path for path in changed if PurePosixPath(path).name in PROMPT_MARKDOWN_NAMES]


def approval_ask_text(path):
    """The text of the ask for a coder's edit to the approval-only file `path`."""
    return (f"`{path}:1` [other] A fix coder edited `{path}`, which needs the user's approval. "
            f"Change: {approval_change(path)}")


def no_code_numbers(findings):
    """The 1-based issue numbers of the findings whose ruling is no code change."""
    return [number for number, finding in enumerate(findings, 1) if is_no_code_finding(finding.text)]


def rejected_ask_records(session_id, repo):
    """The finding records of the asks the session rejected in `repo` (the reviewed repo's top level, the key
    asks-done writes under: the packet's own `--repo`), [] with no session id."""
    rows_repo = handback_store.ruled_rows_repo(repo)
    texts = handback_store.rejected_ask_texts(session_id, rows_repo)
    return [parse_finding(text) for text in texts]


def names_changed_path(finding_path, changed_path, repo):
    """Whether a finding's path (a reviewer's text: repo-relative, a tail of it, or absolute under `repo`) names the
    repo-relative `changed_path`."""
    return names_held_file(held_path_in_repo(finding_path, repo), changed_path)


def ruling_line(finding):
    """One line for the reviewer's list of no-code rulings: the finding's location, then the ruling's note, so a cut
    of a long line never removes the note."""
    return f"{located(finding)} {ruled_note(finding.text)}"


def broken_ruling_finding(ruled, other_paths, path, every_finding_ruled, repo):
    """The finding of the no-code ruling that the change to code file `path` breaks, or None. `ruled` maps each
    no-code issue number to its finding; `other_paths` are the paths the other findings and nits name."""
    named = [finding for _number, finding in sorted(ruled.items()) if names_changed_path(finding.path, path, repo)]
    if every_finding_ruled:
        return named[0] if named else ruled[min(ruled)]
    if any(names_changed_path(other, path, repo) for other in other_paths):
        return None
    return named[0] if named else None


NOT_APPLIED_BLOCKER = "The coder did not apply the adopted plan change ({why}): {ruling}"
SKIPPED_WHY = "it skipped the finding"
NO_DIFF_WHY = "the pass left no fix diff"
NO_FILE_DIFF_WHY = "the pass left no fix diff in the finding's file"
HELD_WHY = "its file is held by another session"
RULED_OUT_WHY = "its file is ruled out of the review"


class Unapplied(NamedTuple):
    finding: object
    blocker: str


def adopted_rulings(rows):
    """{finding text: AdoptedRuling} of the rows `review_loop_prompt_file.header_adopted` reads."""
    fields = handback_store.AdoptedRuling._fields
    return {text: handback_store.AdoptedRuling(**{field: row[field] for field in fields})
            for text, row in rows.items()}


def not_applied_why(finding, number, skips, changed, repo):
    """Why the fix pass left the adopted `finding` unapplied, None when it applied it. It is unapplied when the coder
    skipped it (`number` is in `skips`), left no diff in the finding's file, or, for a finding with no path, left no
    diff at all."""
    if number in skips:
        return SKIPPED_WHY
    if not finding.path:
        return None if changed else NO_DIFF_WHY
    if any(names_changed_path(finding.path, path, repo) for path in changed):
        return None
    return NO_FILE_DIFF_WHY


def unapplied_adopted(findings, adopted, skips, changed, repo):
    """The Unapplied (finding, blocker) of each adopted finding (a text in `adopted`) of a fix pass that the coder
    left unapplied (see `not_applied_why`). Each blocker names the ruling: the marker's who and when, then the
    change."""
    unapplied = []
    for number, finding in enumerate(findings, 1):
        if finding.text not in adopted:
            continue
        why = not_applied_why(finding, number, skips, changed, repo)
        if why is None:
            continue
        blocker = NOT_APPLIED_BLOCKER.format(why=why, ruling=script_utils.one_line(finding.text, None))
        unapplied.append(Unapplied(finding, blocker))
    return unapplied


def withheld_adopted(findings, adopted, kept, held):
    """The Unapplied of each adopted finding among `findings` that the loop withheld from the coder: it is not in
    `kept`; it sits on a held file when it is in `held`, else on a ruled-out file."""
    withheld = []
    for finding in findings:
        if finding.text not in adopted or finding in kept:
            continue
        why = HELD_WHY if finding in held else RULED_OUT_WHY
        blocker = NOT_APPLIED_BLOCKER.format(why=why, ruling=script_utils.one_line(finding.text, None))
        withheld.append(Unapplied(finding, blocker))
    return withheld


def prior_issue_entries(round_findings, skips, put_back_findings):
    """The round's findings as the next reviewers' prior issues: fixed, skipped with the coder's reason, or partial
    when the loop put the file back."""
    entries = []
    for number, item in enumerate(round_findings, 1):
        entry = {"issue": item.text, "status": "fixed", "file": item.path or "unknown"}
        if number in skips:
            entry["status"] = "skipped"
            entry["reason"] = skips[number]
        elif item in put_back_findings:
            entry["status"] = "partial"
            entry["reason"] = "the loop put the file back to keep a recorded ruling"
        entries.append(entry)
    return entries


class RuledFindings:
    def unrecord_ruled_out(self, withheld):
        """Takes each withheld finding out of skipped_fp: it stays open, so the packet carries it once. The host holds
        skipped_fp and given_skipped."""
        withheld_findings = [item.finding for item in withheld]
        kept_entries = []
        for entry in self.skipped_fp:
            ruled_out = entry["reason"] == review_loop_ruled_out.RULED_OUT_REASON
            if ruled_out and entry["item"] in withheld_findings:
                self.given_skipped -= 1
                continue
            kept_entries.append(entry)
        self.skipped_fp = kept_entries

    def init_ruled_state(self):
        # a location-and-note line (`ruling_line`) per finding ruled no code change, for the reviewer prompt
        self.no_code_rulings = []
        self.no_code_broken = []  # {"ruling", "file"} of each code file a coder changed against such a ruling
        self.rejected_asks = []  # records of the asks the session rejected earlier, which a repeat never stops on
        # (ask, reason) of each pointer ask, pass note, repeated ask or repeat of a rejected ask, dropped before the
        # packet
        self.dropped_asks = []
        self.user_only_asks = []  # the approval asks only the user rules; the packet marks each one `user_only`
        self.user_only_paths = []  # the repo-relative path each approval ask was filed for
        # path -> the blob id its edit is measured against, so a coder's own commit of the edit still shows on resume
        self.user_only_bases = {}
        self.approval_blobs = {}  # path -> blob id of each approval-only file before the latest coder pass
        self.user_ruled = []  # the texts of the findings the user accepted, which a fix-first run applies
        self.session_ruled = []  # the texts of the findings a session ruled on; a coder's re-ask of one is a skip
        self.user_ruled_at = ""  # when the fix run was launched, the ruling's time
        self.adopted = {}  # finding text -> the AdoptedRuling of each finding whose plan change a ruling adopted
        self.session_id = ""  # the session whose store holds the rulings; an applied ruling is recorded there

    @property
    def ruled_texts(self):
        """The texts of the findings the user or a session ruled on."""
        return [*self.user_ruled, *self.session_ruled]

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
        text: the handoff's ruling or a finding the user or a session ruled on, either of which settles a plan-drift
        ask on its criterion ids. A repeat goes to the dropped asks."""
        impact_texts = [impact["text"] for impact in self.plan_impacts]
        settling_texts = [*self.resolved_texts, *self.ruled_texts]
        if not repeats_an_ask(item, [*self.asks, *also_earlier], impact_texts, settling_texts):
            return False
        self.drop_asks([item], REPEATED_ASK_REASON)
        return True

    def record_plan_impact(self, impact):
        """Adds one plan impact ({text, gate, ac_change, cause, adopted, applied, settled, reword}). The same text
        again, from a later round or a second reviewer, stays one. `applied` is True when the coder's edits for it
        are already in the tree. `reword` is True for an impact that names a criterion and says `kind: reword`: only
        the criterion's words change, so a standing ruling can cover it. `settled` (default False) marks an impact
        an earlier ruling covers: it is adopted, never printed, and logs no deviation."""
        if any(near_title(entry["text"], impact["text"]) for entry in self.plan_impacts):
            return
        self.plan_impacts.append({"settled": False, **impact})

    def route_plan_items(self, agent, items):
        """(the items the coder fixes this round, the items held for a ruling). A plan impact that changes no
        acceptance criterion is adopted by rule and fixed like any finding; one that changes a criterion, or says
        nothing, is held for the end. An item the handoff's ruling, a carried finding or a finding the user or a session
        ruled on settles (see ruled_plan_impact) is a plain fix; a new one takes the path above. A reword of a
        criterion is a plain fix too, adopted and applied, when the loop's plan holds a standing ruling that covers
        rewords."""
        to_coder, ruling_held = [], []
        for item in items:
            if ruled_plan_impact(item.text, self.resolved_texts, self.ruled_texts):
                to_coder.append(item)
                continue

            ac_change = plan_format.changes_acceptance_criteria(item.text)
            reword = standing_rulings.impact_rewords_criterion(item.text)
            under_standing_ruling = reword and self.standing_reword_ruling() is not None
            adopted = not ac_change or under_standing_ruling
            self.record_plan_impact({"text": item.text, "gate": agent, "ac_change": ac_change,
                                     "cause": plan_format.PLAN_CAUSE, "adopted": adopted,
                                     "applied": False, "reword": reword})
            (ruling_held if ac_change and not under_standing_ruling else to_coder).append(item)
        return to_coder, ruling_held

    def mark_standing_rewords_applied(self, changed):
        """After a coder pass: the reword impacts adopted under a standing ruling count as applied when the pass
        changed the plan's acceptance-criteria file or the plan file. Any other change leaves them unapplied."""
        if not self.plan:
            return
        plan_file = PurePosixPath(self.plan)
        reword_files = {plan_file.as_posix(), plan_file.with_name(plan_format.CRITERIA_FILE_NAME).as_posix()}
        if not reword_files.intersection(changed):
            return
        for impact in self.plan_impacts:
            if impact["adopted"] and impact["reword"] and impact["ac_change"] and not impact["settled"]:
                impact["applied"] = True

    def standing_reword_ruling(self):
        """The standing ruling in the loop's plan that covers rewords, or None with no plan on disk or no such ruling.
        A standing ruling line that does not parse raises PlanFormatError (`file:line:` and the expected form); the
        loop stops on it."""
        if not self.plan:
            return None
        plan_path = Path(self.repo) / self.plan
        if not plan_path.is_file():
            return None
        return standing_rulings.reword_ruling(plan_path)

    def record_coder_plan_impact(self, report, changed):
        """A coder's PLAN-IMPACT report joins the plan impacts. Its edits stay and the loop goes on. A toolkit cause,
        or a cause that does not parse, is never adopted. `changed` holds the files the coder's edits changed. Returns
        True when the impact is held for a ruling. An impact that a ruling or a finding the user or a session ruled
        on settles is recorded as adopted and settled: it is never printed, logs no deviation, and is not held."""
        text = coder_report.plan_impact_block(report) or report.strip()
        cause = plan_format.stopping_plan_impact_cause([text], cause_required=True)
        ac_change = plan_format.changes_acceptance_criteria(text)
        settled = cause == plan_format.PLAN_CAUSE and ruled_plan_impact(text, self.resolved_texts, self.ruled_texts)
        adopted = settled or (not ac_change and cause == plan_format.PLAN_CAUSE)
        self.record_plan_impact({"text": text, "gate": CODER_GATE, "ac_change": ac_change, "cause": cause,
                                 "adopted": adopted, "applied": bool(changed), "settled": settled,
                                 "reword": standing_rulings.impact_rewords_criterion(text)})
        return not adopted and cause != plan_format.TOOLKIT_CAUSE

    def ask_for_approval_only_edits(self, changed, findings):
        """After a coder pass on `findings`: files one ask for the user per approval-only file (see
        `approval_only_paths`) the pass changed. The ask rides the packet's ask list like a reviewer ask: a /code
        phase review's commit gate holds the commit until it is ruled; the run's status is unchanged. The same file in
        a later round stays one ask. A file that a finding the user ruled on names by its repo-relative (or absolute)
        path is not asked about: the ruling is the approval, and a same-named file in another folder still is asked
        about.
        A session's ruling is no approval, except on this ask itself (a revert), which would otherwise be filed
        again."""
        ruled_paths = self.approval_ruled_paths(findings)
        filed = False
        for path in approval_only_paths(changed):
            if path in ruled_paths:
                continue
            self.file_approval_ask(path, self.approval_blobs.get(path))
            filed = True
        if filed:
            self.save_approval_paths()

    def snapshot_approval_blobs(self):
        """Before a coder pass: saves the blob id of each approval-only file's work-tree content (None for a file the
        tree lacks), so the pass's edit is measured against what the file held before it, a phase's own uncommitted
        edit included. A coder's commit of the edit cannot hide it, and a revert to this content clears it."""
        listing = script_utils.git_output(self.repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        if not listing:
            return
        for path in approval_only_paths(listing.split("\0")):
            self.approval_blobs[path] = script_utils.work_tree_blob(self.repo, path)

    def approval_ruled_paths(self, findings):
        """The repo-relative paths that a finding the user ruled on (or a session's accepted approval ask) names."""
        ruling_findings = [finding for finding in findings if self.is_approval_ruling(finding)]
        return {held_path_in_repo(finding.path, self.repo) for finding in ruling_findings}

    def file_approval_ask(self, path, base):
        """Files the user-only ask for approval-only file `path`, whose edit is measured against blob id `base`."""
        ask = parse_finding(approval_ask_text(path))
        self.add_ask(CODER_GATE, ask)
        if ask not in self.user_only_asks:
            self.user_only_asks.append(ask)
        # The filed path itself: parsing it back out of the ask text drops a folder name that holds a space.
        if path not in self.user_only_paths:
            self.user_only_paths.append(path)
        self.user_only_bases.setdefault(path, base)

    def save_approval_paths(self):
        """Saves the paths of the user-only asks on the list, so a run that dies before its packet leaves them for the
        resumed run."""
        write_approval_paths(self.repo, {path: self.user_only_bases[path] for path in self.user_only_paths})

    def resume_approval_asks(self, findings):
        """At the start of a run: files again each approval ask an earlier run saved whose content still differs
        from its saved base blob (committed or not), that no ruling in `findings` settles, and that the session has
        not rejected. Reads only the saved paths, never the change. Rewrites the saved paths with the ones filed
        again, so a settled path leaves the file; with nothing saved, writes nothing."""
        saved = read_approval_paths(self.repo)
        if not saved:
            return
        ruled_paths = self.approval_ruled_paths(findings)
        for path, base in saved.items():
            if path in ruled_paths or not script_utils.content_changed_since(self.repo, path, base):
                continue
            ask = parse_finding(approval_ask_text(path))
            if self.without_rejected([ask]):
                self.file_approval_ask(path, base)
        self.save_approval_paths()

    def is_approval_ruling(self, finding):
        """True when the user ruled on `finding`, or a session accepted the approval ask for its path
        unchanged (a ruling note is no approval)."""
        if finding.text in self.user_ruled:
            return True
        if finding.text not in self.session_ruled:
            return False
        return approval_change(finding.path) in finding.text and ruled_note(finding.text) is None

    def flag_broken_no_code_rulings(self, findings, changed, nits=()):
        """After a coder pass: records the no-code rulings of `findings` for the next reviewer prompt, and each code
        file the pass changed against one in `no_code_ruling_broken`. A changed code file breaks a ruling when only
        no-code findings name it, or when the pass holds nothing but no-code findings (a nit may change code)."""
        numbers = no_code_numbers(findings)
        if not numbers:
            return
        for number in numbers:
            line = ruling_line(findings[number - 1])
            if line not in self.no_code_rulings:
                self.no_code_rulings.append(line)
        code_changed = [path for path in changed if not is_doc_path(path)]
        ruled = {number: findings[number - 1] for number in numbers}
        other_paths = {finding.path for number, finding in enumerate(findings, 1) if number not in ruled}
        other_paths |= {nit.path for nit in nits}
        every_finding_ruled = len(ruled) == len(findings) and not nits
        for path in code_changed:
            broken = broken_ruling_finding(ruled, other_paths, path, every_finding_ruled, self.repo)
            if broken is None:
                continue
            # The coder's issue number is private to its brief; the user sees the ruling's location and note.
            entry = {"ruling": ruling_line(broken), "file": path}
            if entry not in self.no_code_broken:
                self.no_code_broken.append(entry)

    def stop_on_unapplied(self, unapplied):
        """Stops the run as a critical blocker, which plans no reviewer, naming each of the `unapplied` adopted
        findings (see `Unapplied`), and keeps them open. False, with no stop, when there are none."""
        if not unapplied:
            return False
        self.stop("critical-blocker", [item.blocker for item in unapplied])
        self.keep_open([item.finding for item in unapplied])
        return True

    def settle_adopted_after_pass(self, findings, skips, changed):
        """After the fix-first pass on `findings`: (the Unapplied of each adopted ruling the pass left unapplied, the
        1-based numbers of those findings, `skips` without them). The applied findings are recorded as applied. An
        unapplied adopted finding stays open: it is no skipped false positive and no fix."""
        unapplied = unapplied_adopted(findings, self.adopted, skips, changed, self.repo)
        unapplied_findings = [item.finding for item in unapplied]
        # A finding the sign-off put-back undid was not applied, so it is not recorded as applied.
        self.record_applied_adopted(self.not_put_back(item for item in findings if item not in unapplied_findings))
        unapplied_numbers = {number for number, item in enumerate(findings, 1) if item in unapplied_findings}
        kept_skips = {number: line for number, line in skips.items() if number not in unapplied_numbers}
        return unapplied, unapplied_numbers, kept_skips

    def record_applied_adopted(self, findings):
        """Records each adopted finding of an applied fix-first pass as applied in the session's store, so a later fix
        run of the repo is not handed its ruling again."""
        rows_repo = handback_store.ruled_rows_repo(self.repo)
        for finding in findings:
            ruling = self.adopted.get(finding.text)
            if ruling is not None:
                handback_store.record_applied_ruling(self.session_id, ruling, rows_repo)

    def issue_text(self, finding):
        """The finding's text for the coder's issue list, marked when the user accepted the finding. An adopted
        finding carries its own mark."""
        if finding.text in self.adopted or finding.text not in self.user_ruled:
            return finding.text
        return user_ruled_issue(finding.text, self.user_ruled_at)
