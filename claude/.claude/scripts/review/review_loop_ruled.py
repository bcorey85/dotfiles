"""review_loop_ruled.py: what a review loop does with asks it drops, with findings the user already ruled on, and with
a coder's edit to an approval-only file (it reverts the edit and reports it; each finding on that file becomes a
user-only ask carrying the wanted change), as a mixin for `LoopRun`. The one exception is an edit to the scripts
CLAUDE.md that only adds or updates owner bullets (`owner_lines.owner_lines_only`) under a standing ruling that covered
owner lines before the pass: it stays and is reported in the dropped asks. The host class holds asks, plan_impacts,
resolved_texts, files_touched, repo and plan (the plan's path in repo, or ""), and provides `add_ask`. The mixin sets
`owner_file_before` (the scripts CLAUDE.md text before the latest pass) and `owner_line_ruling` (the ruling read
before it) on the host."""
import dataclasses
import pathlib
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import coder_report
import handback_store
import hook_input
import owner_lines
import plan_format
import review_loop_ruled_out
import script_utils
import standing_rulings
from approval_asks_store import (
    UNKNOWN_BASE,
    approval_change,
    read_held_changes,
    read_saved_asks,
    wanted_edit_target,
    wanted_entry,
    write_saved_asks,
)
from finding_record import parse_finding
from format_files import PROMPT_MARKDOWN_NAMES
from review_asks import rejected_ask_text
from review_loop_findings import (
    KEPT_OWNER_LINE_EDIT_REASON,
    NOTE_ASK_REASON,
    REJECTED_ASK_REASON,
    REPEATED_ASK_REASON,
    REVERTED_APPROVAL_EDIT_REASON,
    ask_parts,
    inert_change_marks,
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
    AGENTS.md). A coder never changes these without the user's approval, so each edit is reverted and reported, or
    asked about when it cannot be reverted, unless a ruling covers it (see `ask_for_approval_only_edits`,
    `keeps_owner_line_edit`)."""
    return [path for path in changed if PurePosixPath(path).name in PROMPT_MARKDOWN_NAMES]


def approval_ask_text(path):
    """The text of the ask for a coder's edit to the approval-only file `path`."""
    return (f"`{path}:1` [other] A fix coder edited `{path}`, which needs the user's approval. "
            f"Change: {approval_change(path)}")


def kept_owner_line_text(path):
    """The text of the dropped-ask row for an owner-line edit to `path` that the loop kept. It holds no change and no
    question, so the packet proposes no revert for it."""
    return f"`{path}:1` [other] owner-line edit kept"


def no_code_numbers(findings):
    """The 1-based issue numbers of the findings whose ruling is no code change."""
    return [number for number, finding in enumerate(findings, 1) if is_no_code_finding(finding.text)]


def adopted_numbers(findings, adopted):
    """The 1-based issue numbers of the findings whose text is a key of `adopted`."""
    return [number for number, finding in enumerate(findings, 1) if finding.text in adopted]


def rejected_ask_records(session_id, repo):
    """The finding records of the asks the session rejected in `repo` (the reviewed repo's top level, the key
    asks-done writes under: the packet's own `--repo`), [] with no session id."""
    rows_repo = handback_store.ruled_rows_repo(repo)
    texts = handback_store.rejected_ask_texts(session_id, rows_repo)
    return [parse_finding(text) for text in texts]


def rejected_ask_questions(session_id, repo):
    """The question of each ask the session rejected in `repo`, read from the `question` field its row carries; a row
    with no such field is left out. A comment ask's question names its file, so no path is read from the text."""
    rows_repo = handback_store.ruled_rows_repo(repo)
    rows = handback_store.rejected_ask_rows(session_id, rows_repo)
    return [row["question"] for row in rows if row.get("question")]


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


def not_applied_blocker(why, finding_text):
    """The blocker line for the adopted `finding_text` that the coder did not apply, for the reason `why`."""
    return NOT_APPLIED_BLOCKER.format(why=why, ruling=script_utils.one_line(finding_text, None))


class Unapplied(NamedTuple):
    finding: object
    blocker: str


def adopted_rulings(rows):
    """{finding text: AdoptedRuling} of the rows `review_loop_prompt_file.header_adopted` reads."""
    fields = handback_store.AdoptedRuling._fields
    return {text: handback_store.AdoptedRuling(**{field: row[field] for field in fields})
            for text, row in rows.items()}


def not_applied_why(finding, number, skips, changed, repo, already_applied=()):
    """Why the fix pass left the adopted `finding` unapplied, None when it applied it. It is unapplied when the coder
    skipped it (`number` is in `skips`), left no diff in the finding's file, or, for a finding with no path, left no
    diff at all. A number in `already_applied` is one the coder reported as already in the tree: it needs no diff."""
    if number in already_applied:
        return None
    if number in skips:
        return SKIPPED_WHY
    if not finding.path:
        return None if changed else NO_DIFF_WHY
    if any(names_changed_path(finding.path, path, repo) for path in changed):
        return None
    return NO_FILE_DIFF_WHY


def unapplied_adopted(findings, adopted, skips, changed, repo, already_applied=()):
    """The Unapplied (finding, blocker) of each adopted finding (a text in `adopted`) of a fix pass that the coder
    left unapplied (see `not_applied_why`). Each blocker names the ruling: the marker's who and when, then the
    change."""
    unapplied = []
    for number, finding in enumerate(findings, 1):
        if finding.text not in adopted:
            continue
        why = not_applied_why(finding, number, skips, changed, repo, already_applied)
        if why is None:
            continue
        blocker = not_applied_blocker(why, finding.text)
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
        blocker = not_applied_blocker(why, finding.text)
        withheld.append(Unapplied(finding, blocker))
    return withheld


def prior_issue_entries(round_findings, skips, put_back_findings, reverted_findings=()):
    """The round's findings as the next reviewers' prior issues: fixed, skipped with the coder's reason, or partial
    when the loop put the file back. A finding filed on a reverted approval-only path (`reverted_findings`) reads as
    skipped."""
    entries = []
    for number, item in enumerate(round_findings, 1):
        entry = {"issue": item.text, "status": "fixed", "file": item.path or "unknown"}
        if item in reverted_findings:
            entry["status"] = "skipped"
            entry["reason"] = REVERTED_APPROVAL_EDIT_REASON
        elif number in skips:
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
        self.rejected_questions = []  # the stored question field of each of them
        # (ask, reason) of each pointer ask, pass note, repeated ask or repeat of a rejected ask, dropped before the
        # packet
        self.dropped_asks = []
        # the approval asks the session may not rule (anything but a rejected on a wanted-change ask); the packet
        # marks each one `user_only`
        self.user_only_asks = []
        self.user_only_paths = []  # the repo-relative path each approval ask was filed for
        # path -> the blob id its edit is measured against
        self.user_only_bases = {}
        self.approval_blobs = {}  # path -> blob id of each approval-only file before the latest coder pass
        # path -> the index entry of each approval-only file before the latest coder pass (None: not in the index)
        self.approval_index_entries = {}
        self.approval_head_before = None  # the commit HEAD named before the latest coder pass
        self.approval_snapshot_ok = False  # whether the latest snapshot could list the repo's files
        self.approval_unhashed = set()  # approval-only files the latest snapshot could not hash or index-read
        # work-tree text of the scripts CLAUDE.md before the latest pass (None: absent, unhashed, unreadable, unlisted)
        self.owner_file_before = None
        # the standing ruling that covers owner lines, read before the latest pass (None: none, or no such file)
        self.owner_line_ruling = None
        # each wanted-change ask on the list, saved with the paths (shape: `read_saved_asks`)
        self.wanted_entries = []
        # the saved wanted-change entries that a kept held packet waits on; no ask is filed for them
        self.kept_held_wanted = []
        # path -> base of each saved approval path that a kept held packet waits on; no ask is filed for it
        self.kept_held_bases = {}
        self.user_ruled = []  # the texts of the findings the user accepted, which a fix-first run applies
        self.session_ruled = []  # the texts of the findings a session ruled on; a coder's re-ask of one is a skip
        self.user_ruled_at = ""  # when the fix run was launched, the ruling's time
        self.adopted = {}  # finding text -> the AdoptedRuling of each finding whose plan change a ruling adopted
        self.adopted_unapplied = []  # the ruling text of each adopted finding the loop stopped on as unapplied
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
            under_standing_ruling = (reword
                                     and self.standing_ruling_covering(standing_rulings.COVERS_REWORDS) is not None)
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

    def standing_ruling_covering(self, covers):
        """The standing ruling in the loop's plan that covers `covers`, or None with no plan on disk or no such
        ruling. A standing ruling line that does not parse raises PlanFormatError (`file:line:` and the
        expected form); the loop stops on it."""
        plan_path = self.plan_path_on_disk()
        if plan_path is None:
            return None
        return standing_rulings.first_ruling_covering(plan_path, covers)

    def plan_path_on_disk(self):
        """The loop's plan file as a Path, or None with no plan or no such file."""
        if not self.plan:
            return None
        plan_path = Path(self.repo) / self.plan
        if not plan_path.is_file():
            return None
        return plan_path

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
        """After a coder pass on `findings`: reverts the pass's edit to each approval-only file (see
        `approval_only_paths`) and reports it in the dropped asks (see `revert_approval_edit`). Returns the paths it
        reverted. A reverted edit files one user-only ask per finding on that path (see `ask_for_wanted_changes`); an
        edit that cannot be reverted files the revert ask for the user. Both ride the packet's ask
        list like a reviewer ask: a /code phase review opens it for `phase_asks.py` to rule on; the run's
        status is unchanged. The revert ask for the same file in a later round stays one ask; a wanted-change ask
        stays one per finding and file, and a repeat of a rejected one is dropped, not filed. A file that a finding
        the user ruled on names by its repo-relative (or absolute) path, or a wanted-change ask the user accepted
        names (see `wanted_edit_target`), is left as edited: the ruling is the approval, and a same-named file in
        another folder still is reverted.
        A session's ruling is no approval, except on this ask itself (a revert), which would otherwise be filed
        again. An owner-line edit to the scripts CLAUDE.md under a pre-pass standing ruling stays (see
        `keeps_owner_line_edit`)."""
        ruled_paths = self.approval_ruled_paths(findings)
        filed = False
        reverted = []
        for path in approval_only_paths(changed):
            if path in ruled_paths or self.names_ruled_wanted_target(path, findings):
                continue
            if self.keeps_owner_line_edit(path):
                continue
            if self.revert_approval_edit(path):
                reverted.append(path)
                continue
            self.file_approval_ask(path, self.approval_base(path))
            filed = True
        wanted_filed = self.ask_for_wanted_changes(findings, reverted)
        if filed or wanted_filed:
            self.save_approval_paths()
        return reverted

    def ask_for_wanted_changes(self, findings, reverted):
        """Files a user-only ask for each finding on a reverted approval-only path, carrying the finding's proposed
        change: the file stays at its pre-pass text, so the user decides whether the wanted edit is made. Each
        question names the file and the finding. The asks have no saved base: nothing of the file is left to
        restore. A reverted edit that no finding names files no ask: it stays in the dropped asks. A change ends
        with `wanted_edit_target`, which names the exact path. Returns whether it filed any."""
        filed = False
        for finding in self.findings_on_reverted_paths(findings, reverted):
            path = held_path_in_repo(finding.path, self.repo)
            changes = []
            for part in finding.each_part:
                part_change = ask_parts(part.text).change
                changes.append(inert_change_marks(part_change))
            change = "; ".join(changes)
            line = finding.line or 1
            ask = parse_finding(f"`{path}:{line}` [{finding.finding_class}] A fix coder wants to edit "
                                f"`{path}` for the finding \"{finding.title}\", which needs the user's approval. "
                                f"Change: {change} {wanted_edit_target(path)}")
            filed = self.file_wanted_ask(ask, path, line, finding.title) or filed
        return filed

    def file_wanted_ask(self, ask, path, line, title):
        """Files `ask`, for the exact repo-relative `path` at `line` and the finding `title`, as a
        user-only ask the loop saves. The ask's location is set from `path` and `line`, because the location parser
        reads no path with a space in a folder name. Nothing is filed when the list, or the asks saved for a kept held
        packet (`kept_held_wanted`), hold an ask for the same finding on the file already (a later round's pass
        edits the same file again, whatever the line), or when the session rejected the same ask (see
        `rejected_by_title`). Returns whether it was filed."""
        if self.repeats_a_wanted_ask(path, title):
            return False
        ask = dataclasses.replace(ask, path=path, line=line)
        if self.rejected_by_title(ask):
            self.drop_asks([ask], REJECTED_ASK_REASON)
            return False
        self.add_ask(CODER_GATE, ask)
        if ask not in self.user_only_asks:
            self.user_only_asks.append(ask)
        entry = wanted_entry(ask.text, ask_parts(ask.text).change, path, line, title)
        if entry not in self.wanted_entries:
            self.wanted_entries.append(entry)
        return True

    def repeats_a_wanted_ask(self, path, title):
        """Whether a wanted-change ask on the list, or saved for a kept held packet (`kept_held_wanted`), names
        `path` and the same finding `title`. The title must be equal: a near match would merge two short unrelated
        findings into one ask and lose one."""
        listed = self.wanted_entries + self.kept_held_wanted
        return any(entry["path"] == path and entry["title"] == title for entry in listed)

    def rejected_by_title(self, ask):
        """Whether the session rejected this wanted-change ask: a rejection has the same title, whatever the line the
        finding sits on. The title is built from the question, which names the file, so the stored location is not
        compared (it is UNLOCATED for a path whose folder holds a space). The question is mostly fixed wording, so a
        near match would drop another finding's ask."""
        stored = rejected_ask_text({"question": ask_parts(ask.text).question, "file_line": located(ask)})
        stored_title = parse_finding(stored).title
        return any(rejected.title == stored_title for rejected in self.rejected_asks)

    def approval_base(self, path):
        """The base a filed ask for `path` saves: its pre-pass blob id, None for a file the pass created, or
        `UNKNOWN_BASE` when the snapshot could not list the files, or could not hash this one or read its
        index entry."""
        if not self.approval_snapshot_ok or path in self.approval_unhashed:
            return UNKNOWN_BASE
        return self.approval_blobs.get(path)

    def keeps_owner_line_edit(self, path):
        """True when the pass's edit to `path` stays: `path` is the scripts CLAUDE.md, a standing ruling covered owner
        lines before the pass, and the edit only adds or updates owner bullets. The kept edit is reported in the
        dropped asks. Fail closed: a missing ruling, missing pre-pass text, an unreadable file, or an index entry or
        commit whose content differs from the work tree returns False, and the edit is reverted. It touches neither the
        index nor HEAD."""
        if path != owner_lines.SCRIPTS_CLAUDE_MD:
            return False
        if self.owner_line_ruling is None or self.owner_file_before is None:
            return False
        after = hook_input.read_file_text(Path(self.repo) / path)
        if after is None:
            return False
        if not owner_lines.owner_lines_only(self.owner_file_before, after):
            return False
        if not self.staged_and_committed_match_work_tree(path):
            return False
        label = standing_rulings.ruling_label(self.owner_line_ruling)
        reason = KEPT_OWNER_LINE_EDIT_REASON.format(ruling=label)
        self.drop_asks([parse_finding(kept_owner_line_text(path))], reason)
        return True

    def staged_and_committed_match_work_tree(self, path):
        """Whether the index entry of `path` is its pre-pass entry or holds the work-tree blob, and, when the pass
        committed `path`, HEAD holds the work-tree blob. Otherwise the index or HEAD holds content the work tree
        does not show, and the revert must run."""
        work_blob = script_utils.work_tree_blob(self.repo, path)
        if work_blob is None:
            return False
        try:
            index_now = script_utils.index_entry(self.repo, path)
        except script_utils.GitCallError:
            return False
        index_blob = index_now.blob if index_now else None
        if index_now != self.approval_index_entries.get(path) and index_blob != work_blob:
            return False
        if not self.committed_during_pass(path):
            return True
        head_blob = script_utils.blob_at_commit(self.repo, script_utils.head_commit(self.repo), path)
        return head_blob == work_blob

    def revert_approval_edit(self, path):
        """Puts approval-only file `path` back to its pre-pass blob (deletes a file the pass created) and records the
        edit in the dropped asks under `REVERTED_APPROVAL_EDIT_REASON`. Returns True when the file needs no ask: it
        was reverted, or the pass left its content as it was. False when the revert failed or the pre-pass content
        is unknown (the snapshot could not list the files, or could not hash this one or read its index entry), or
        git cannot read its index entry now, so the edit stays and is asked about (fail closed). A path the snapshot
        did not list was created by the pass.
        The index entry goes back to its pre-pass entry when the pass changed it (a `git add` of the edit). When the
        pass committed the edit, the work tree goes back as above and the path joins `files_touched`, so the session
        commits the revert."""
        base = self.approval_base(path)
        if base == UNKNOWN_BASE:
            return False
        content_changed = script_utils.content_changed_since(self.repo, path, base)
        index_before = self.approval_index_entries.get(path)
        try:
            index_now = script_utils.index_entry(self.repo, path)
        except script_utils.GitCallError:
            return False
        index_changed = index_now != index_before
        committed = self.committed_during_pass(path)
        if not (content_changed or index_changed or committed):
            return True
        if content_changed and not script_utils.restore_blob(self.repo, path, base):
            return False
        if index_changed and not script_utils.restore_index_entry(self.repo, path, index_before):
            return False
        if committed:
            self.files_touched.add(path)
        self.drop_asks([parse_finding(approval_ask_text(path))], REVERTED_APPROVAL_EDIT_REASON)
        return True

    def findings_on_reverted_paths(self, findings, reverted):
        """The `findings` whose path is one of the `reverted` approval-only paths: their fix lived in an edit the loop
        put back, so none of them is fixed."""
        reverted_paths = set(reverted)
        return [finding for finding in findings if held_path_in_repo(finding.path, self.repo) in reverted_paths]

    def keep_unreverted_open(self, findings, reverted):
        """Keeps `findings` open except those on a reverted approval-only path: those are filed as user-only asks, or
        dropped as a repeat of a rejected one.
        Returns the findings on a reverted path. The host has keep_open and drop_open."""
        reverted_findings = self.findings_on_reverted_paths(findings, reverted)
        self.drop_open(reverted_findings)
        self.keep_open([item for item in findings if item not in reverted_findings])
        return reverted_findings

    def committed_during_pass(self, path):
        """Whether the latest coder pass committed a change to `path`: HEAD holds another blob for it than the commit
        HEAD named before the pass did."""
        head_now = script_utils.head_commit(self.repo)
        if self.approval_head_before is None or head_now == self.approval_head_before:
            return False
        blob_before = script_utils.blob_at_commit(self.repo, self.approval_head_before, path)
        return script_utils.blob_at_commit(self.repo, head_now, path) != blob_before

    def snapshot_approval_blobs(self):
        """Before a coder pass: saves the blob id of each approval-only file's work-tree content (None for a file the
        tree lacks), so the pass's edit is measured against what the file held before it, a phase's own uncommitted
        edit included. Within the pass, a coder's commit of the edit cannot hide it, and a revert to this content
        clears it. An existing file whose hash fails, or whose index entry git cannot list, goes to
        `approval_unhashed`, never stored as absent. When the
        scripts CLAUDE.md is listed, also saves its text and the standing ruling that covers owner lines, both read
        before the pass so a ruling the pass writes grants nothing to that same pass; a malformed ruling line raises
        PlanFormatError."""
        self.owner_file_before = None
        self.owner_line_ruling = None
        self.approval_blobs = {}
        self.approval_index_entries = {}
        self.approval_head_before = script_utils.head_commit(self.repo)
        self.approval_unhashed = set()
        self.approval_snapshot_ok = False
        listing = script_utils.repo_file_paths(self.repo)
        if listing is None:
            return
        self.approval_snapshot_ok = True
        paths = approval_only_paths(listing)
        try:
            entries = script_utils.index_entries(self.repo, paths)
        except script_utils.GitCallError:
            self.approval_unhashed.update(paths)
            return
        for path in paths:
            blob = script_utils.work_tree_blob(self.repo, path, keep_object=True)
            if blob is None and (pathlib.Path(self.repo) / path).is_file():
                self.approval_unhashed.add(path)
                continue
            self.approval_blobs[path] = blob
            self.approval_index_entries[path] = entries[path]
        if self.approval_blobs.get(owner_lines.SCRIPTS_CLAUDE_MD) is None:
            return
        self.owner_file_before = hook_input.read_file_text(Path(self.repo) / owner_lines.SCRIPTS_CLAUDE_MD)
        if self.owner_file_before is None:
            # Fail closed: with no pre-pass text the edit is reverted as before.
            return
        self.owner_line_ruling = self.standing_ruling_covering(standing_rulings.COVERS_OWNER_LINES)

    def approval_ruled_paths(self, findings):
        """The repo-relative paths that a finding the user ruled on (or a session's accepted approval ask) names."""
        ruling_findings = [finding for finding in findings if self.is_approval_ruling(finding)]
        return {held_path_in_repo(finding.path, self.repo) for finding in ruling_findings}

    def names_ruled_wanted_target(self, path, findings):
        """True when a finding the user ruled on is an accepted wanted-change ask for exactly `path`. The finding's
        own location is empty (UNLOCATED) for a path whose folder holds a space, so the run reads the path from these
        words and `approval_ruled_paths` misses that path."""
        target = wanted_edit_target(path)
        return any(self.is_approval_ruling(finding) and target in finding.text for finding in findings)

    def file_approval_ask(self, path, base):
        """Files the user-only ask for approval-only file `path`, whose edit is measured against `base`, as
        `approval_base` returns it."""
        ask = parse_finding(approval_ask_text(path))
        self.add_ask(CODER_GATE, ask)
        if ask not in self.user_only_asks:
            self.user_only_asks.append(ask)
        # The filed path itself: parsing it back out of the ask text drops a folder name that holds a space.
        if path not in self.user_only_paths:
            self.user_only_paths.append(path)
        self.user_only_bases.setdefault(path, base)

    def drop_approval_asks(self, paths):
        """Takes back the approval asks filed for `paths`, whose edits a put-back removed, and saves the rest."""
        for path in paths:
            filed = parse_finding(approval_ask_text(path))
            if filed in self.user_only_asks:
                self.user_only_asks.remove(filed)
            if filed in self.asks:
                self.asks.remove(filed)
            self.ask_gates.pop(filed, None)
            self.user_only_paths.remove(path)
            self.user_only_bases.pop(path, None)
        if paths:
            self.save_approval_paths()

    def save_approval_paths(self):
        """Saves the paths of the user-only approval asks and the wanted-change asks on the list, so a run that dies
        before its packet leaves them for the resumed run. The paths of the asks a kept held packet waits on stay,
        with their bases, and so do the wanted-change entries it waits on (`kept_held_wanted`): the user's ruling on
        that packet restores the file from its base."""
        paths = {**self.kept_held_bases, **{path: self.user_only_bases[path] for path in self.user_only_paths}}
        write_saved_asks(self.repo, paths, self.kept_held_wanted + self.wanted_entries)

    def resume_approval_asks(self, findings):
        """At the start of a run: files again each approval ask an earlier run saved whose content still differs
        from its saved base blob (an unknown base counts as changed), that no ruling in `findings` settles, and that
        the session has not rejected, and whose file still differs from HEAD (a file that matches HEAD, reverted or
        committed, files no ask), and that no kept held packet waits on. It also files again the saved
        wanted-change asks (see `resume_wanted_asks`), reading their change. Rewrites both the saved paths and the
        saved wanted asks with the ones filed again, so a settled one leaves the file; a path or wanted-change ask a
        kept held packet waits on stays saved (a path with its base). With nothing saved, writes nothing."""
        saved, wanted = read_saved_asks(self.repo)
        if not saved and not wanted:
            return
        ruled_paths = self.approval_ruled_paths(findings)
        # The kept packet owns a held change, and the user's ruling on that packet drops it from the record.
        held_changes = read_held_changes(self.repo)
        self.resume_wanted_asks(wanted, held_changes)
        for path, base in saved.items():
            if approval_change(path) in held_changes:
                self.kept_held_bases[path] = base
                continue
            if path in ruled_paths:
                continue
            if base != UNKNOWN_BASE and not script_utils.content_changed_since(self.repo, path, base):
                continue
            if script_utils.matches_head(self.repo, path):
                continue
            ask = parse_finding(approval_ask_text(path))
            if self.without_rejected([ask]):
                self.file_approval_ask(path, base)
        self.save_approval_paths()

    def resume_wanted_asks(self, wanted, held_changes):
        """Files again each saved wanted-change ask (see `ask_for_wanted_changes`) that no kept held packet waits on
        and that the session has not rejected. A ruled one left the saved file when it was ruled. A held one stays
        saved in `kept_held_wanted`, so a later pass does not file it a second time."""
        for entry in wanted:
            if entry["change"] in held_changes:
                self.kept_held_wanted.append(entry)
                continue
            self.file_wanted_ask(parse_finding(entry["text"]), entry["path"], entry["line"], entry["title"])

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
        self.adopted_unapplied = [self.adopted[item.finding.text].text for item in unapplied]
        self.keep_open([item.finding for item in unapplied])
        return True

    def settle_adopted_after_pass(self, findings, skips, changed, adopted_applied=frozenset()):
        """After the fix-first pass on `findings`: (the Unapplied of each adopted ruling the pass left unapplied, the
        1-based numbers of those findings, `skips` without them and without the adopted findings reported ALREADY
        APPLIED: such a finding counts as applied even when the coder also wrote SKIPPED for it). The applied findings
        are recorded as applied. An unapplied adopted finding stays open: it is no skipped false positive and no fix."""
        unapplied = unapplied_adopted(findings, self.adopted, skips, changed, self.repo, adopted_applied)
        unapplied_findings = [item.finding for item in unapplied]
        # A finding the sign-off put-back undid was not applied, so it is not recorded as applied.
        self.record_applied_adopted(self.not_put_back(item for item in findings if item not in unapplied_findings))
        unapplied_numbers = {number for number, item in enumerate(findings, 1) if item in unapplied_findings}
        dropped = unapplied_numbers | adopted_applied
        kept_skips = {number: line for number, line in skips.items() if number not in dropped}
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
