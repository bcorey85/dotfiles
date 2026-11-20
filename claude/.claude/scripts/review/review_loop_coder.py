"""review_loop_coder.py: the review loop's fix-coder call. It snapshots the tree around the call, records the
untracked files the coder wrote, notes the held files that changed, and returns the diffs of what it changed. Putting
back the untracked files a call deleted is the guard in review_loop_untracked, which wraps every model call."""
import difflib
import pathlib
import typing

import review_loop_held
import review_loop_ruled_out
import review_loop_untracked
import script_utils
from review_loop_calls import claude_call
from review_loop_closure import FIX_DIFF_STATS
from review_loop_plan import changed_files_since

DIFF_CONTEXT = 12


def coder_fault_notes():
    """The notes the loop's model calls left for the packet's tool_fault: untracked files a call removed, held files
    a coder changed."""
    return [*review_loop_untracked.UNTRACKED_FAULTS, *review_loop_held.HELD_FAULTS,
            *review_loop_ruled_out.RULED_OUT_FAULTS]


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


def coder_call(role, prompt, repo, out, held, pass_guard):
    """The fix coder. Returns a CoderResult (report, diffs, changed): the diffs of what it changed feed the round-two
    brief, and one diff file per changed path under `out` (listed in the global FIX_DIFF_STATS) feeds the
    class-closure check; changed lists the paths whose text differs. A held file that changed during the call is
    left as it is and noted, and never counts as changed. `pass_guard` (a review_loop_ruled_out.PassGuard) undoes
    the pass's edits to ruled-out files and its unnamed deletions before the tree is read again. A commit the coder
    made during the call is kept; its changes count against the commit HEAD named before the call. A failed call
    raises CoderCallError naming the files it changed before it died."""
    head_before = script_utils.head_commit(repo)
    before = script_utils.without_paths(file_texts(repo), held)
    untracked = review_loop_untracked.unheld_untracked(repo, held)
    held_before = review_loop_held.digests(repo, held)
    try:
        report = claude_call(role, prompt, repo, out, agent="coder", deletable=pass_guard.deletions)
    except RuntimeError as error:
        pass_guard.undo()
        review_loop_untracked.record_loop_written(repo, held, untracked)
        after = after_call(role, repo, held, held_before, head_before)
        changed = changed_paths(before, after)
        if not changed:
            raise CoderCallError(str(error), []) from error
        raise failed_call_error(error, changed) from error

    pass_guard.undo()
    review_loop_untracked.record_loop_written(repo, held, untracked)
    after = after_call(role, repo, held, held_before, head_before)
    diffs = write_fix_diffs(repo, out, role, before, after, head_before)
    changed = changed_paths(before, after)
    return CoderResult(report, diffs, changed)


def after_call(role, repo, held, held_before, head_before):
    """Notes the held files that changed, and returns the snapshot of the tree without the held files, against the
    commit HEAD named before the call."""
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
    return text_diff(path, old_text, after.get(path, ""))


def text_diff(path, old_text, new_text):
    """The unified diff lines of one path from `old_text` to `new_text`; [] when they are the same."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    return list(difflib.unified_diff(old_lines, new_lines, old_label(path), f"b/{path}", n=DIFF_CONTEXT, lineterm=""))


def old_label(path):
    """The label of the old side of a path's diff."""
    return f"a/{path}"


def fix_diff_file(out, role, path):
    """The file that holds one path's diff of the pass `role`."""
    return pathlib.Path(out) / "fix-diffs" / role / f"{path}.diff"


def result_without_paths(result, paths, out, role):
    """The coder result without `paths`: their changed entries, diff texts, diff files and FIX_DIFF_STATS rows."""
    headers = {f"--- {old_label(path)}" for path in paths}
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
