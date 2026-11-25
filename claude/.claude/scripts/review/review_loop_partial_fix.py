"""review_loop_partial_fix.py: the record of a fix coder that died mid-edit. The tree may hold part of the fix and
nothing says which findings landed, so the loop saves the findings it gave the coder, less those on a reverted
approval-only path (a user-only ask now), and the diff the coder left
(`PARTIAL_FIX_NAME`, in the review-fix folder of the repo's git dir so the next launch on the repo finds it; no record
when git names no git dir). Each path's diff is the coder's own, read before any sign-off or comment lines were put
back; a path the put-back returned to its old text, or the loop reverted, has no diff in the record. The
stop note names those findings as unverified. The next launch sends those not on a held file to the coder again, and
keeps only the held ones in the record after that pass, or when none of its findings is left to send (no diff then); a
run that stops before the first fix pass leaves the record as it is. The record names
the branch it was written on (null when git failed, "" on a detached HEAD), and a launch on another branch
stops; a null branch, or a branch git cannot name at launch, skips that check.

`PartialFixRuns` is the `LoopRun` mixin that sets the record in memory: a settle or a dead pass changes
`pending_record`, and the run's single write at the end saves it.

Owner of the dead-coder record. Import it; never read or write the record another way."""
import json
import typing

import script_utils
from approval_asks_store import review_fix_file
from review_fix_names import PARTIAL_FIX_NAME
from review_loop_pass_names import is_finding_pass
from review_loop_prompt_file import PromptFileError
from review_loop_put_back import fully_put_back_paths

FINDINGS_FIELD = "findings"
DIFF_FIELD = "diff"
TIME_FIELD = "time"
BRANCH_FIELD = "branch"


def write_partial_fix(repo, finding_texts, diffs, now):
    """Saves the record: the `finding_texts` the coder was given, the pass diff (`diffs` maps each changed path to
    its diff text), the time `now` and the repo's branch. Writes nothing when git names no review-fix folder."""
    record_file = review_fix_file(repo, PARTIAL_FIX_NAME)
    if record_file is None:
        return
    record_file.parent.mkdir(parents=True, exist_ok=True)
    diff_text = "\n".join(diffs[path] for path in sorted(diffs))
    record = {FINDINGS_FIELD: list(finding_texts), DIFF_FIELD: diff_text, TIME_FIELD: now,
              BRANCH_FIELD: script_utils.current_branch(repo)}
    script_utils.write_text_atomically(record_file, json.dumps(record, indent=2) + "\n")


class PendingRecord(typing.NamedTuple):
    """What the record is to hold when the run ends: the finding `texts` and the `diffs` (path to diff text). No
    texts means the record is deleted."""

    texts: list
    diffs: dict


class DeadPassRecord(typing.NamedTuple):
    """The result of a dead coder pass: the words the stop note adds and the record to save at the end of the run
    (None when the pass leaves the record as it is)."""

    note: str
    pending: PendingRecord | None


def dead_pass_record(repo, call_name, findings, reverted_findings, saved, held_unfixed, kept_error):
    """After the coder pass `call_name` died: the stop note words and the pending record. A pass that is not a
    finding pass (its prompt comes from a check's output, which the next launch runs again) saves nothing. The
    `findings` the coder was given, less the `reverted_findings` (user-only asks now), are unverified; the `saved`
    texts on a held file (an entry of `held_unfixed`, no coder got them) stay in the record. `kept_error` holds the
    pass diffs. With no finding at all the record is deleted: an older record would send user-only asks to the
    coder again."""
    if not is_finding_pass(call_name):
        return DeadPassRecord("", None)
    recorded_texts = [item.text for item in findings if item not in reverted_findings]
    held_texts = held_saved_texts(saved, held_unfixed)
    if not recorded_texts and not held_texts:
        return DeadPassRecord("", PendingRecord([], {}))
    pending = PendingRecord([*recorded_texts, *held_texts], kept_error.diffs)
    if not recorded_texts:
        return DeadPassRecord("", pending)
    record_file = review_fix_file(repo, PARTIAL_FIX_NAME)
    return DeadPassRecord(unverified_note(recorded_texts, record_file, bool(kept_error.changed)), pending)


def unverified_note(finding_texts, record_file, tree_changed):
    """The words the stop note adds: each of the `finding_texts` (the findings the coder was given, less those on a
    reverted approval-only path) is unverified (the tree holds part of the fix only when `tree_changed`), and where
    the `record_file` is, when one is saved."""
    listed = "; ".join(finding_texts)
    if tree_changed:
        note = f" The tree may hold part of the fix, so each of these findings is unverified: {listed}."
    else:
        note = f" Each of these findings is unverified: {listed}."
    if record_file is None:
        return note
    saved = "them and the partial diff" if tree_changed else "them"
    return (f"{note} The loop saved {saved} in {record_file}; the next launch on this repo sends "
            "them to the coder again.")


class SavedRecordError(PromptFileError):
    """The saved record cannot be used: it does not read, or it was written on another branch. The message names the
    file to delete."""


def saved_findings(repo):
    """The finding texts of the repo's saved record, [] when there is none. A record that does not read names the
    file and the expected form; one written on another branch names both branches and the delete command."""
    record_file = review_fix_file(repo, PARTIAL_FIX_NAME)
    if record_file is None or not record_file.is_file():
        return []
    expected = (f"a JSON object with a {FINDINGS_FIELD} list of non-empty finding texts; "
                f"delete {record_file} to drop the record")
    try:
        record = json.loads(record_file.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SavedRecordError(f"{record_file}: {error}; expected {expected}") from error
    texts = record.get(FINDINGS_FIELD) if isinstance(record, dict) else None
    if not script_utils.is_nonblank_string_list(texts):
        raise SavedRecordError(f"{record_file}: expected {expected}")
    branch = script_utils.current_branch(repo)
    recorded_branch = record.get(BRANCH_FIELD)
    if recorded_branch is None or branch is None:
        return texts
    if recorded_branch != branch:
        recorded_name = recorded_branch or "detached HEAD"
        launch_name = branch or "detached HEAD"
        raise SavedRecordError(f"{record_file}: the record was written on branch {recorded_name} and this launch is "
                               f"on branch {launch_name}; delete {record_file} to drop the record")
    return texts


def saved_findings_not_in_header(saved, findings):
    """The `saved` record texts that the header's `findings` lack: they go to the coder with the header's."""
    return [text for text in saved if text not in findings]


def held_saved_texts(saved, held_unfixed):
    """The `saved` texts that sit on a held file (an entry of `held_unfixed`): no coder got them, so they stay in the
    record."""
    held_texts = [entry["item"].text for entry in held_unfixed]
    return [text for text in saved if text in held_texts]


def settle_if_finding_pass(call_name, saved, held_unfixed):
    """After the coder pass `call_name` ran: the pending record when it took the `saved` findings (a finding pass
    with saved texts), else None. The coder was sent every saved finding except those on a held file (an entry of
    `held_unfixed`), which stay in the record for the next launch with no diff, because the pass left the old one out
    of date."""
    if not saved or not is_finding_pass(call_name):
        return None
    return PendingRecord(held_saved_texts(saved, held_unfixed), {})


def save_pending(repo, pending, at):
    """Writes the `pending` record at time `at`, once at the end of a run; deletes the record when it holds no
    texts. None leaves the record as it is."""
    if pending is None:
        return
    if not pending.texts:
        remove_partial_fix(repo)
        return
    write_partial_fix(repo, pending.texts, pending.diffs, at)


def remove_partial_fix(repo):
    """Deletes the repo's saved record."""
    record_file = review_fix_file(repo, PARTIAL_FIX_NAME)
    if record_file is not None:
        record_file.unlink(missing_ok=True)


def coder_failure_blocker(call_name, error, scope_guard_failed=False, died=True):
    """The blocker for a failed coder pass: what failed, that its findings were not all applied, and the way out.
    `scope_guard_failed` is true when the scope guard failed before any coder ran, so none were applied. `died` is
    false when the call finished and the loop could not undo all of its pass."""
    if scope_guard_failed:
        what_failed = f"the {call_name} pass could not start: the scope guard could not read the repo"
    elif not died:
        what_failed = f"the {call_name} coder pass finished but the loop could not undo all of it"
    else:
        what_failed = f"the {call_name} coder call failed"
    return (f"{what_failed}: {error}. Its findings were not all applied "
            "and are in findings_remaining. Never apply them outside the review loop: "
            "a fix made outside it is unreviewed. "
            "Fix the cause of the failure and rerun the review.")


class PartialFixRuns:
    """The partial-fix record of a run, as a mixin for `LoopRun`. The host class holds repo, held_unfixed,
    files_touched and pending_record, and has undo_protected_edits, flag_broken_no_code_rulings,
    ask_for_approval_only_edits, keep_coder_commit_in_scope, keep_unreverted_open."""

    # The findings of the saved record that no coder pass or settle has answered yet. A tuple or a list the run
    # replaces on each change, so no instance shares it.
    saved_record_texts = ()

    def settle_saved_after_pass(self, call_name):
        """After the coder pass `call_name` ran: settles the saved record when the pass took its findings."""
        settled = settle_if_finding_pass(call_name, self.saved_record_texts, self.held_unfixed)
        if settled is None:
            return
        self.pending_record = settled
        self.saved_record_texts = settled.texts

    def settle_saved_without_coder(self):
        """When no coder pass will take the saved findings (every one is held, ruled out or otherwise answered
        before the coder): only the ones on a held file stay in the record, and a record with none is dropped at
        the end of the run. Sets the pending record only; the run writes once at its end."""
        if not self.saved_record_texts:
            return
        held_texts = held_saved_texts(self.saved_record_texts, self.held_unfixed)
        self.pending_record = PendingRecord(held_texts, {})
        self.saved_record_texts = held_texts

    def failed_pass_blocker(self, call_name, error, snapshots, findings, nits):
        """The stop text of a coder pass that died, or that finished while the loop could not undo all of
        it: puts the protected lines back, settles the findings and the files the pass touched, and sets the
        record a pass that carried findings leaves at the end of the run."""
        signoffs, comments = snapshots
        put_back = self.undo_protected_edits(signoffs, comments, findings)
        changed = [path for path in error.changed if path not in fully_put_back_paths(put_back)]
        self.flag_broken_no_code_rulings(findings, changed, nits)
        reverted = self.ask_for_approval_only_edits(changed, findings)
        kept = [path for path in changed if path not in reverted]
        self.files_touched.update(kept)
        self.keep_coder_commit_in_scope()
        reverted_findings = self.keep_unreverted_open(findings, reverted)
        kept_error = error.keeping_only(kept)
        blocker = coder_failure_blocker(call_name, kept_error, died=error.died)
        dead = dead_pass_record(self.repo, call_name, findings, reverted_findings, self.saved_record_texts,
                                self.held_unfixed, kept_error)
        if dead.pending is not None:
            self.pending_record = dead.pending
        return blocker + dead.note
