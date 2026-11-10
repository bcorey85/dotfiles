"""review_loop_coder.py: the review loop's fix-coder call. It snapshots the tree around the call, puts back the
untracked files the coder deleted, notes the held files that changed, and returns the diffs of what it changed."""
import difflib
import pathlib
import typing

import file_backup
import review_loop_held
import script_utils
from review_loop_calls import claude_call
from review_loop_closure import FIX_DIFF_STATS
from review_loop_plan import changed_files_since, head_commit, scope

DIFF_CONTEXT = 12
# One note per fix call that deleted an untracked file it did not make, for the packet's tool_fault.
UNTRACKED_FAULTS = []


def coder_fault_notes():
    """The notes the coder calls left for the packet's tool_fault: untracked files lost, held files changed."""
    return [*UNTRACKED_FAULTS, *review_loop_held.HELD_FAULTS]


def file_texts(repo, start=None):
    """{path: text} of the changed files on disk: against HEAD, or against the commit `start` once HEAD moved off it,
    so a fix the coder committed during the call still reads as changed."""
    files, _origins, _base = changed_files_since(repo, start)
    texts = {}
    for path in files:
        target = pathlib.Path(repo) / path
        if target.is_file():
            texts[path] = target.read_text(errors="replace")
    return texts


class CoderCallError(RuntimeError):
    """A coder call that failed after it may have edited the tree. `changed` lists the paths whose text differs."""

    def __init__(self, message, changed):
        super().__init__(message)
        self.changed = changed


def changed_paths(before, after):
    """The sorted paths whose text differs between two file_texts snapshots; a missing path reads as empty text."""
    return sorted(path for path in set(before) | set(after) if before.get(path, "") != after.get(path, ""))


def put_back_untracked(role, backup):
    """A fix call may edit an untracked file but never delete one it did not make. Writes back each one that
    vanished, and notes it in UNTRACKED_FAULTS; a file too large to have been saved is noted as lost."""
    restored, lost = file_backup.restore_missing(backup)
    if restored:
        UNTRACKED_FAULTS.append(f"{role} deleted untracked files it did not make; the loop restored "
                                + ", ".join(restored))
    if lost:
        UNTRACKED_FAULTS.append(f"{role} deleted untracked files too large to save, so they are gone: "
                                + ", ".join(lost))


class CoderResult(typing.NamedTuple):
    """A fix coder's report, the diffs of what it changed, and the paths whose text differs."""

    report: str
    diffs: list
    changed: list


def failed_call_error(error, changed):
    """The CoderCallError for a coder call that died after it changed `changed` paths."""
    message = (f"{error}; it changed {', '.join(changed)} before it died, so the tree holds a partial fix "
               "that may fail its checks")
    return CoderCallError(message, changed)


def coder_call(role, prompt, repo, out, held):
    """The fix coder. Returns a CoderResult (report, diffs, changed): the diffs of what it changed feed the round-two
    brief, and one diff file per changed path under `out` (listed in the global FIX_DIFF_STATS) feeds the
    class-closure check; changed lists the paths whose text differs. A held file that changed during the call is
    left as it is and noted, and never counts as changed. A commit the coder made during the call is kept; its changes
    count against the commit HEAD named before the call. A failed call raises CoderCallError naming the files it
    changed before it died."""
    head_before = head_commit(repo)
    before = script_utils.without_paths(file_texts(repo), held)
    untracked = [path for path, entry in scope(repo).items() if entry[1] == "??" and path not in held]
    backup = file_backup.save_files(repo, untracked)
    held_before = review_loop_held.digests(repo, held)
    try:
        report = claude_call(role, prompt, repo, out, agent="coder")
    except RuntimeError as error:
        after = after_call(role, repo, held, backup, held_before, head_before)
        changed = changed_paths(before, after)
        if not changed:
            raise
        raise failed_call_error(error, changed) from error

    after = after_call(role, repo, held, backup, held_before, head_before)
    diffs = write_fix_diffs(repo, out, role, before, after, head_before)
    changed = changed_paths(before, after)
    return CoderResult(report, diffs, changed)


def after_call(role, repo, held, backup, held_before, head_before):
    """Puts back the untracked files the coder deleted, notes the held files that changed, and returns the snapshot
    of the tree without the held files, against the commit HEAD named before the call."""
    put_back_untracked(role, backup)
    review_loop_held.note_changed(role, repo, held_before)
    texts = file_texts(repo, head_before)
    return script_utils.without_paths(texts, held)


def path_diff(repo, path, before, after, base):
    """The unified diff lines of one path between two file_texts snapshots; `base` is the commit HEAD named before
    the call, or None in a repo with no commit."""
    # A file clean before the call diffs against its text in `base`, not against nothing.
    if path in before:
        old_text = before[path]
    else:
        base_text = script_utils.git_output(repo, "show", f"{base}:{path}") if base else None
        old_text = base_text or ""
    old_lines = old_text.splitlines()
    new_lines = after.get(path, "").splitlines()
    return list(difflib.unified_diff(old_lines, new_lines, f"a/{path}", f"b/{path}", n=DIFF_CONTEXT, lineterm=""))


def record_fix_diff(out, role, path, difference):
    """Writes one path's diff file under `out` and adds its line counts to FIX_DIFF_STATS."""
    diff_file = out / "fix-diffs" / role / f"{path}.diff"
    diff_file.parent.mkdir(parents=True, exist_ok=True)
    diff_file.write_text("\n".join(difference))
    added = sum(1 for line in difference if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in difference if line.startswith("-") and not line.startswith("---"))
    FIX_DIFF_STATS.append({"path": path, "added": added, "removed": removed, "diff_file": str(diff_file)})


def write_fix_diffs(repo, out, role, before, after, base):
    """One diff file per changed path under `out`, listed in FIX_DIFF_STATS. Returns the diff texts."""
    diffs = []
    for path in sorted(set(before) | set(after)):
        difference = path_diff(repo, path, before, after, base)
        if not difference:
            continue
        diffs.append("\n".join(difference))
        record_fix_diff(out, role, path, difference)
    return diffs
