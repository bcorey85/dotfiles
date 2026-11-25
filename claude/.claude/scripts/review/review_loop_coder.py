"""review_loop_coder.py: the review loop's fix-coder call. It snapshots the tree around the call, records the
untracked files the coder wrote, notes the held files that changed, and returns the diffs of what it changed. Putting
back the untracked files a call deleted is the guard in review_loop_untracked, which wraps every model call."""
import difflib
import pathlib
import typing

import review_loop_held
import review_loop_ruled_out
import review_loop_ruling_check
import review_loop_scope_guard
import review_loop_untracked
import script_utils
from review_loop_calls import ModelCallError, claude_call
from review_loop_closure import FIX_DIFF_STATS
from review_loop_plan import changed_files_since

DIFF_CONTEXT = 12


def coder_fault_notes():
    """The notes the loop's model calls left for the packet's tool_fault: untracked files a call removed, held files
    a coder changed, ruled-out files put back, out-of-scope files put back, a failed put-back step, out-of-scope
    files the loop could not copy and ruling checks that could not judge a pass."""
    return [*review_loop_untracked.UNTRACKED_FAULTS, *review_loop_held.HELD_FAULTS,
            *review_loop_ruled_out.RULED_OUT_FAULTS, *review_loop_scope_guard.SCOPE_FAULTS,
            *review_loop_ruling_check.RULING_CHECK_FAULTS]


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


class NoFinalReportError(ModelCallError):
    """A coder call that exited 0 and printed no final report."""


# The errors a guard's undo may raise; each one becomes a CoderCallError.
UNDO_ERRORS = (RuntimeError, OSError)


class GuardUndoError(RuntimeError):
    """The pass guard's undo failed and the scope guard's undo failed too; the message holds both errors."""


class CoderCallError(RuntimeError):
    """A coder call that died, or finished while the loop could not undo all of its pass (`died` False), after it may
    have edited the tree. `changed` lists the paths whose text differs; `diffs` maps each of them to its diff text."""

    def __init__(self, message, changed, cause=None, diffs=None, died=True):
        super().__init__(message)
        self.changed = changed
        self.cause = message if cause is None else cause
        self.diffs = {} if diffs is None else diffs
        self.died = died

    def keeping_only(self, kept):
        """This error as it reads when only the `kept` paths still hold the coder's edits."""
        kept_diffs = {path: self.diffs[path] for path in kept if path in self.diffs}
        return failed_call_error(self.cause, kept, kept_diffs, self.died)


def changed_paths(before, after):
    """The sorted paths whose text differs between two file_texts snapshots; a missing path reads as empty text."""
    return sorted(path for path in set(before) | set(after) if before.get(path, "") != after.get(path, ""))


class CoderResult(typing.NamedTuple):
    """A fix coder's report, the diffs of what it changed, the paths whose text differs, and the approval-only paths
    whose edit the loop reverted (`without_reverted` took them out of the first three)."""

    report: str
    diffs: list
    changed: list
    reverted: tuple = ()


def without_reverted(result, reverted, stats_before):
    """`result` without the `reverted` paths in its changed list and without their diffs, so a reverted edit counts
    as no change. Also drops the FIX_DIFF_STATS entries of those paths that its own coder call appended (the ones
    from index `stats_before` on) and deletes their diff files, so the class-closure check is not told about an edit
    that is gone. An earlier round's entry for the same path stays: its edit was kept."""
    this_call_stats = FIX_DIFF_STATS[stats_before:]
    reverted_stats = [stat for stat in this_call_stats if stat["path"] in reverted]
    for stat in reverted_stats:
        pathlib.Path(stat["diff_file"]).unlink(missing_ok=True)
    kept_stats = [stat for stat in this_call_stats if stat["path"] not in reverted]
    FIX_DIFF_STATS[stats_before:] = kept_stats
    reverted_headers = [f"--- {diff_old_label(path)}\n" for path in reverted]
    kept_diffs = [diff for diff in result.diffs if not diff.startswith(tuple(reverted_headers))]
    kept_changed = [path for path in result.changed if path not in reverted]
    return result._replace(diffs=kept_diffs, changed=kept_changed, reverted=tuple(reverted))


def failed_call_error(error, changed, diffs=None, died=True):
    """The CoderCallError for a coder call that changed `changed` paths (`diffs` maps each to its diff text) and then
    died (`died`), or finished while the loop could not undo all of its pass. With none changed, the error names only
    the cause."""
    if not changed:
        return CoderCallError(str(error), [], died=died)
    outcome = "before it died" if died else "during the pass"
    message = (f"{error}; it changed {', '.join(changed)} {outcome}, so the tree holds a partial fix "
               "that may fail its checks")
    return CoderCallError(message, changed, str(error), diffs, died)


def coder_call(role, prompt, repo, out, held, pass_guard, scope_guard, model=""):
    """The fix coder. Returns a CoderResult (report, diffs, changed): the diffs of what it changed feed the round-two
    brief, and one diff file per changed path under `out` (listed in the global FIX_DIFF_STATS) feeds the
    class-closure check; changed lists the paths whose text differs. A held file that changed during the call is
    left as it is and noted, and never counts as changed. `pass_guard` (a review_loop_ruled_out.PassGuard) undoes
    the pass's edits to ruled-out files and its unnamed deletions before the tree is read again, and `scope_guard`
    (a review_loop_scope_guard.ScopeGuard) puts back the files outside the pass's scope. A commit the coder
    made during the call is kept; its changes count against the commit HEAD named before the call. A failed call
    raises CoderCallError naming the files it changed before it died, and so does a call whose guards could not undo
    the pass. `model` is the model the coder runs on; "" leaves the agent's own."""
    head_before = script_utils.head_commit(repo)
    before = script_utils.without_paths(file_texts(repo), held)
    untracked = review_loop_untracked.unheld_untracked(repo, held)
    held_before = review_loop_held.digests(repo, held)
    try:
        report = claude_call(role, prompt, repo, out, agent="coder", model=model or None,
                             deletable=pass_guard.deletions)
        if not report.strip():
            # A coder that exits 0 with no final report left its findings unverified, as a crash does.
            raise NoFinalReportError(f"the {role} call ended with no final report")
    except ModelCallError as error:
        undo_failure, after = settle_call(role, repo, held, pass_guard, scope_guard, untracked, held_before,
                                          head_before)
        changed = changed_paths(before, after)
        diffs = pass_diffs(repo, changed, before, after, head_before)
        if undo_failure is not None:
            raise failed_call_error(f"{error}; undoing the pass failed: {undo_failure}", changed, diffs) from error
        raise failed_call_error(error, changed, diffs) from error

    undo_failure, after = settle_call(role, repo, held, pass_guard, scope_guard, untracked, held_before, head_before)
    changed = changed_paths(before, after)
    if undo_failure is not None:
        diffs = pass_diffs(repo, changed, before, after, head_before)
        raise failed_call_error(str(undo_failure), changed, diffs, died=False) from undo_failure
    diffs = write_fix_diffs(repo, out, role, before, after, head_before)
    return CoderResult(report, diffs, changed)


def pass_diffs(repo, changed, before, after, head_before):
    """{path: diff text} of each `changed` path between the tree texts before and after a coder call."""
    return {path: "\n".join(path_diff(repo, path, before, after, head_before)) for path in changed}


def settle_call(role, repo, held, pass_guard, scope_guard, untracked, held_before, head_before):
    """After a coder call: undoes the pass with the two guards, records the files the loop wrote, and reads the tree.
    Returns (undo failure or None, the tree texts after the call). `held_before` and `head_before` are the held
    digests and the head commit taken before the call."""
    undo_failure = failed_undo(pass_guard, scope_guard)
    review_loop_untracked.record_loop_written(repo, held, untracked)
    after = after_call(role, repo, held, held_before, head_before)
    return undo_failure, after


def failed_undo(pass_guard, scope_guard):
    """The error a guard raised while undoing the pass of a coder call, or None when both undid it; the caller reads
    the tree and turns a failure into a CoderCallError, so `repair` can catch it."""
    try:
        undo_pass(pass_guard, scope_guard)
    except UNDO_ERRORS as undo_error:
        return undo_error
    return None


def undo_pass(pass_guard, scope_guard):
    """Undoes what the pass may not keep: the ruled-out files and unnamed deletions, then the files out of scope."""
    try:
        pass_guard.undo()
    except UNDO_ERRORS as pass_error:
        undo_scope_after_failure(pass_error, scope_guard)
        raise
    scope_guard.undo()


def undo_scope_after_failure(pass_error, scope_guard):
    """Runs the scope guard's undo after the pass guard failed, so the out-of-scope files are not left unrestored and
    unnoted. Raises one joined error when that undo fails too; returns when it works, and the caller re-raises."""
    try:
        scope_guard.undo()
    except UNDO_ERRORS as scope_error:
        raise GuardUndoError(f"{pass_error}; {scope_error}") from scope_error


def after_call(role, repo, held, held_before, head_before):
    """Notes the held files that changed, and returns the snapshot of the tree without the held files, against the
    commit HEAD named before the call."""
    review_loop_held.note_changed(role, repo, held_before)
    texts = file_texts(repo, head_before)
    return script_utils.without_paths(texts, held)


def diff_old_label(path):
    """The label that heads the old side of the unified diff of `path`."""
    return f"a/{path}"


def path_diff(repo, path, before, after, base):
    """The unified diff lines of one path between two file_texts snapshots; `base` is the commit HEAD named before
    the call, or None in a repo with no commit."""
    # A file clean before the call diffs against its text in `base`, not against nothing.
    if path in before:
        old_text = before[path]
    else:
        base_text = script_utils.git_output(repo, "show", f"{base}:{path}") if base else None
        old_text = base_text or ""
    return text_diff(path, old_text, after.get(path, ""))


def text_diff(path, old_text, new_text):
    """The unified diff lines of one path from `old_text` to `new_text`; [] when they are the same."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    return list(difflib.unified_diff(old_lines, new_lines, diff_old_label(path), f"b/{path}", n=DIFF_CONTEXT,
                                     lineterm=""))


def fix_diff_file(out, role, path):
    """The file that holds one path's diff of the pass `role`, always under `out`: an absolute `path` would make
    pathlib drop `out`, so its leading slash is cut."""
    relative = str(path).lstrip("/")
    return pathlib.Path(out) / "fix-diffs" / role / f"{relative}.diff"


def result_without_paths(result, paths, out, role):
    """The coder result without `paths`: their changed entries, diff texts, diff files and FIX_DIFF_STATS rows."""
    headers = {f"--- {diff_old_label(path)}" for path in paths}
    diffs = [diff for diff in result.diffs if diff.split("\n", 1)[0] not in headers]
    changed = script_utils.without_paths(result.changed, paths)
    diff_files = {str(fix_diff_file(out, role, path)) for path in paths}
    FIX_DIFF_STATS[:] = [row for row in FIX_DIFF_STATS if row["diff_file"] not in diff_files]
    for diff_file in diff_files:
        pathlib.Path(diff_file).unlink(missing_ok=True)
    return result._replace(changed=changed, diffs=diffs)


def result_with_path_text(result, path, old_text, new_text, out, role):
    """The coder result with `path` read as changed from `old_text` to `new_text`: its diff text, diff file and
    FIX_DIFF_STATS row recomputed, and the path left out of `changed` when the two texts are the same."""
    without = result_without_paths(result, [path], out, role)
    difference = text_diff(path, old_text, new_text)
    if not difference:
        return without
    record_fix_diff(out, role, path, difference)
    return without._replace(changed=[*without.changed, path], diffs=[*without.diffs, "\n".join(difference)])


def record_fix_diff(out, role, path, difference):
    """Writes one path's diff file under `out` and adds its line counts to FIX_DIFF_STATS."""
    diff_file = fix_diff_file(out, role, path)
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
