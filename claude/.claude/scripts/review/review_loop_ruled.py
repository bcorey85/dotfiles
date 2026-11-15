"""review_loop_ruled.py: what a review loop does with asks it drops, with findings the user already ruled on, and with
a coder's edit to an approval-only file (it files an ask), as a mixin for `LoopRun`. The host class holds asks,
plan_impacts and resolved_texts, and provides `add_ask`."""
from pathlib import PurePosixPath

import coder_report
import handback_store
import plan_format
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


def approval_change(path):
    """The change the approval ask proposes for `path`. An accepted ask reaches the next fix run as
    `<file_line> [<class>] Proposed change: <change>`, so the change is the part that names the ask there."""
    return f"revert the fix coder's edit to `{path}`."


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


class RuledFindings:
    def init_ruled_state(self):
        # a location-and-note line (`ruling_line`) per finding ruled no code change, for the reviewer prompt
        self.no_code_rulings = []
        self.no_code_broken = []  # {"ruling", "file"} of each code file a coder changed against such a ruling
        self.rejected_asks = []  # records of the asks the session rejected earlier, which a repeat never stops on
        # (ask, reason) of each pointer ask, pass note, repeated ask or repeat of a rejected ask, dropped before the
        # packet
        self.dropped_asks = []
        self.user_ruled = []  # the texts of the findings the user accepted, which a fix-first run applies
        self.session_ruled = []  # the texts of the findings a session ruled on; a coder's re-ask of one is a skip
        self.user_ruled_at = ""  # when the fix run was launched, the ruling's time

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
        nothing, is held for the end. An item the handoff's ruling, a carried finding or a finding the user or a session
        ruled on settles (see ruled_plan_impact) is a plain fix; a new one takes the path above."""
        to_coder, ruling_held = [], []
        for item in items:
            if ruled_plan_impact(item.text, self.resolved_texts, self.ruled_texts):
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
        True when the impact is held for a ruling. An impact that a ruling or a finding the user or a session ruled
        on settles is recorded as adopted and settled: it is never printed, logs no deviation, and is not held."""
        text = coder_report.plan_impact_block(report) or report.strip()
        cause = plan_format.stopping_plan_impact_cause([text], cause_required=True)
        ac_change = plan_format.changes_acceptance_criteria(text)
        settled = cause == plan_format.PLAN_CAUSE and ruled_plan_impact(text, self.resolved_texts, self.ruled_texts)
        adopted = settled or (not ac_change and cause == plan_format.PLAN_CAUSE)
        self.record_plan_impact({"text": text, "gate": CODER_GATE, "ac_change": ac_change, "cause": cause,
                                 "adopted": adopted, "applied": bool(changed), "settled": settled})
        return not adopted and cause != plan_format.TOOLKIT_CAUSE

    def ask_for_approval_only_edits(self, changed, findings):
        """After a coder pass on `findings`: files one ask for the user per approval-only file (see
        `approval_only_paths`) the pass changed. The ask rides the packet's ask list like a reviewer ask: a /code
        phase review's commit gate holds the commit until it is ruled; the run's status is unchanged. The same file in
        a later round stays one ask. A file that a finding the user ruled on names is not asked about: the ruling is
        the approval. A session's ruling is no approval, except on this ask itself (a revert), which would otherwise
        be filed again."""
        ruling_findings = [finding for finding in findings if self.is_approval_ruling(finding)]
        for path in approval_only_paths(changed):
            if any(names_changed_path(finding.path, path, self.repo) for finding in ruling_findings):
                continue
            text = approval_ask_text(path)
            self.add_ask(CODER_GATE, parse_finding(text))

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

    def issue_text(self, finding):
        """The finding's text for the coder's issue list, marked when the user accepted the finding."""
        if finding.text not in self.user_ruled:
            return finding.text
        return user_ruled_issue(finding.text, self.user_ruled_at)
