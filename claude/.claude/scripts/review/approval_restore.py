"""approval_restore.py: what an accepted approval ask does to the file it names. The ask proposes to revert a
fix coder's edit to an approval-only file (see `approval_asks_store.approval_change`). The saved approval paths hold
the blob the file had before that pass, so accepting the ask puts the file back to it: uncommitted lines the user
kept stay, which a reset to HEAD would drop. An ask whose base is unknown (`UNKNOWN_BASE`), or whose saved base is
None while HEAD tracks the path, is not restored here: it still reaches the fix coder as a finding.
Owner of what an accepted approval ask does to its file; import it for that restore. The post-pass revert of a fix
coder's edit is `RuledFindings.revert_approval_edit`."""
import shlex
from typing import NamedTuple

import script_utils
from approval_asks_store import UNKNOWN_BASE, approval_path_of_change, is_approval_ask, read_approval_paths
from ask_outcome_words import ACCEPTED, APPLIED
from review_fix_names import RESTORED_INDEXES_KEY
from review_fix_state import UsageError


class ApprovalRestoreError(Exception):
    """A file could not be put back to its pre-pass blob."""


def restorable_paths(repo, asks, outcomes):
    """The saved approval paths to restore, as a list of (index of the ask, path, base blob id or None for a file
    the pass created). Only an `accepted` approval ask whose saved base is known, and is not None while HEAD
    tracks the path, is in it. Reads the saved paths and changes nothing."""
    accepted = [index for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True))
                if outcome == ACCEPTED and is_approval_ask(item)]
    if not accepted:
        return []
    saved = read_approval_paths(repo)
    restores = []
    for index in accepted:
        # Read from the change text, which is written from the exact filed path: parsing the path back out of the
        # ask's location drops a folder name that holds a space.
        path = approval_path_of_change(asks[index].get("change"))
        if path not in saved or saved[path] == UNKNOWN_BASE:
            continue
        if saved[path] is None and script_utils.blob_at_commit(repo, "HEAD", path) is not None:
            # A file saved before unknown bases had their own value: None may mean "unknown" for a tracked file, so
            # deleting it could drop the user's uncommitted lines.
            continue
        restores.append((index, path, saved[path]))
    return restores


class RestoredApproval(NamedTuple):
    ask_index: int
    path: str


def restore_accepted_approvals(repo, asks, outcomes):
    """Puts each file of an accepted approval ask back to its saved pre-pass blob (deleting a file the pass
    created) and returns a RestoredApproval (ask index, path) for each one restored. Raises ApprovalRestoreError
    naming the file, its pre-pass blob (or that the pass created it, for a file to delete) and the way out at the
    first restore that fails: the caller logs nothing then, and a rerun restores again."""
    restored = []
    for index, path, base in restorable_paths(repo, asks, outcomes):
        if not script_utils.restore_blob(repo, path, base):
            if base is None:
                raise ApprovalRestoreError(
                    f"cannot delete `{path}` (the pass created it). Fix the file's write access and rerun")
            if script_utils.git_output(repo, "cat-file", "-e", base) is None:
                # The saved blob is an unreferenced loose object, so `git gc` can prune it.
                raise ApprovalRestoreError(
                    f"cannot restore `{path}`: its saved pre-pass blob {base} was pruned from the git store. "
                    f"Restore `{path}` by hand")
            raise ApprovalRestoreError(
                f"cannot restore `{path}` to its pre-pass blob {base}. Fix the file's write access and rerun")
        restored.append(RestoredApproval(index, path))
    return restored


def refuse_corrections_of_state(state, indexes, outcomes):
    """Raises UsageError, with nothing logged, for a corrected approval ask of the saved `state` that
    cannot be undone or redone. Every first ruling drops the ask's saved pre-pass base, so a correction to
    `accepted` has nothing to restore from, and a reset to HEAD would drop the user's uncommitted lines. An ask whose
    file asks-done restored was put back to its pre-pass text, so a correction cannot keep the coder's edit. Only
    the asks at `indexes` are looked at."""
    asks = state["asks"]
    restored_indexes = saved_restored_indexes(state)
    for index in indexes:
        item = asks[index]
        path = approval_path_of_change(item.get("change"))
        if path is None:
            continue
        if outcomes[index] == ACCEPTED:
            raise UsageError(
                f"cannot restore `{path}`: its pre-pass text is not saved. Restore your own lines in `{path}` by "
                f"hand before the coder runs, then answer the ask `modified:<the edit>`, with the edit naming "
                f"`{path}`, in place of `accepted`. Nothing was logged.")
        if index in restored_indexes:
            raise UsageError(
                f"cannot change the ruling on `{path}`: the accepted ruling already put the file back to its "
                "pre-pass text, and the coder's edit was not saved. The `accepted` ruling stays logged for this ask. "
                "To correct the other asks, repeat this ask's logged answer unchanged. Nothing was logged.")


def restored_lines(restored):
    """One line per restored file, for the session that ruled: the file in its tree changed. The restore writes the
    work tree only, so an index entry staged before it may still hold the coder's edit."""
    return [f"Restored `{item.path}` to its text from before the fix pass; commit it with the rest of the change. "
            f"If the file was staged, stage it again with `git add {shlex.quote(item.path)}`."
            for item in restored]


def saved_restored_indexes(state):
    """The ask indexes a saved packet or state records as restored, as a set."""
    return set(state.get(RESTORED_INDEXES_KEY) or [])


def finding_outcomes(state):
    """The saved `state`'s ask outcomes with each restored approval ask marked APPLIED."""
    return outcomes_without_restored(state["ask_outcomes"], saved_restored_indexes(state))


def outcomes_without_restored(outcomes, restored_indexes):
    """The outcomes with each restored approval ask marked APPLIED: it has nothing left for the coder, so it stays
    out of the findings file."""
    return [APPLIED if index in restored_indexes else outcome for index, outcome in enumerate(outcomes)]


def restore_for_asks_done(target, repo, outcomes):
    """The asks-done step: restores each accepted approval ask of `target`, prints the restored lines, saves the
    restored ask indexes on `target` and returns the outcomes the findings file is built from. Raises UsageError,
    with nothing logged, when a restore fails. A repo of None means no ask is an approval ask, so it is never read.
    A retry after a logging failure restores nothing, as the first call already did and the saved paths are gone, so
    the new indexes join the saved ones: they are never overwritten."""
    try:
        restored = restore_accepted_approvals(repo, target["asks"], outcomes)
    except ApprovalRestoreError as error:
        raise UsageError(
            f"{error}. Or answer the ask `modified:<the edit>` or `rejected`. Nothing was logged.") from error
    for line in restored_lines(restored):
        print(line)
    restored_indexes = saved_restored_indexes(target) | {item.ask_index for item in restored}
    target[RESTORED_INDEXES_KEY] = sorted(restored_indexes)
    return outcomes_without_restored(outcomes, restored_indexes)
