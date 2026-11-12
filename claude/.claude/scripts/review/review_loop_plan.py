"""review_loop_plan.py: the files a scripted review loop reviews, the lines its change adds, and which reviewers go
out in each round."""
import pathlib

import change_removal
import numstat
import script_utils
import source_paths
import worktree_snapshot

LARGE_ADDED_LINES = source_paths.LARGE_ADDED_LINES
LENS_A = ("Own state and lifecycle: UI state while an action is pending, after close or cancel, and on re-open; "
          "stale async results arriving late; cache invalidation after writes. Trace each changed handler through "
          "every state it can be entered from.")
LENS_B = ("Own inputs and surfaces: edge inputs (empty, zero, huge, malformed, duplicate); layout, CSS and "
          "accessibility of every changed element; contracts with unchanged code the change reuses or sits next to. "
          "Read the whole enclosing function and every unchanged helper the change calls.")
# The [added, status] of a named file that has no change in the review's range.
UNCHANGED_ENTRY = (0, "M")


def scope(repo):
    """{path: [added, status]} for the working tree against HEAD, untracked files included."""
    files = {}
    for path, change in worktree_snapshot.working_tree_changes(repo).items():
        status = change["code"].strip()
        files[path] = [change["added"], "??" if status == "??" else status[0]]
    return files


def base_scope(repo, base):
    """{path: [added, status]} for the working tree against the base commit, commits since it and untracked files
    included."""
    numstat_text = script_utils.git_output(repo, "diff", "--numstat", "-z", "--no-renames", base)
    status_text = script_utils.git_output(repo, "diff", "--name-status", "-z", "--no-renames", base)
    if numstat_text is None or status_text is None:
        raise RuntimeError(f"`git diff {base}` failed in {repo}")

    counts = numstat.changed_lines_by_path(numstat_text)
    fields = status_text.split("\0")
    files = {}
    for status, path in zip(fields[0::2], fields[1::2], strict=False):
        if path:
            files[path] = [counts.get(path, (0, 0))[0], status[0]]
    for path, entry in scope(repo).items():
        if entry[1] == "??":
            files[path] = entry
    return files


def changed_files_since(repo, start):
    """(files, origins, base) for the working tree against the commit `start`: the changed files, the rename origin of
    each, and the revision the lines are measured against. A HEAD still at `start`, or a `start` of None, diffs against
    HEAD with renames followed; a HEAD that moved diffs against `start` itself."""
    head = script_utils.head_commit(repo)
    if start is None or head == start:
        return scope(repo), worktree_snapshot.status_entries(repo)[1], "HEAD"
    return base_scope(repo, start), {}, start


def counted_texts(repo, paths):
    """{path: text of the file now} for each of `paths` that counts toward size; a missing file reads as empty."""
    texts = {}
    for path in paths:
        if not source_paths.counts_toward_size(path):
            continue

        target = pathlib.Path(repo) / path
        texts[path] = target.read_text(errors="replace") if target.is_file() else ""
    return texts


def lines_added_since(repo, changes):
    """{path: Counter of the source lines the working tree adds to the base of `changes`} (the result of
    `changed_files_since`), for the files that count toward size. A HEAD that moved diffs against the loop's start
    commit, so lines committed since then still count as added."""
    files, origins, base = changes

    added_by_file = {}
    for path, tree_text in counted_texts(repo, files).items():
        base_path = origins.get(path, path)
        base_text = script_utils.git_output(repo, "show", f"{base}:{base_path}") or ""
        added = change_removal.added_lines(base_text, tree_text, path)
        if added:
            added_by_file[path] = added
    return added_by_file


class ChangeUnderReview:
    """The lines the working tree adds when the loop starts, measured against the commit HEAD names then. The loop
    reads `removed` after every coder pass; a commit made while the loop runs leaves that base where it was."""

    def __init__(self, repo):
        self.repo = repo
        self.start = script_utils.head_commit(repo)
        changes = changed_files_since(repo, self.start)
        self.added = lines_added_since(repo, changes)
        self.start_texts = counted_texts(repo, changes[0])

    def lines_added_by_fixes(self, changes):
        """{path: Counter} of the source lines the tree holds now that it did not hold when the loop started."""
        added_by_file = {}
        # A file a pass put back to the base drops out of the changed files, so the files of the start count too.
        files = changes[0].keys() | self.start_texts.keys()
        for path, now_text in counted_texts(self.repo, sorted(files)).items():
            before_text = self.start_texts.get(path)
            if before_text is None:
                before_text = script_utils.git_output(self.repo, "show", f"{self.start}:{path}") or ""
            added = change_removal.added_lines(before_text, now_text, path)
            if added:
                added_by_file[path] = added
        return added_by_file

    def removed(self):
        """{path: count} of the added lines the tree no longer adds. A line a fix pass added to any file, even one
        that already held the same line, is kept."""
        changes = changed_files_since(self.repo, self.start)
        now_added = lines_added_since(self.repo, changes)
        return change_removal.removed_by_file(self.added, now_added, self.lines_added_by_fixes(changes))


def review_files(repo, base="", only=()):
    """The files under review: the working tree against HEAD, or against `base` when one is given. With `only`, just
    those paths, each with its entry in that range or UNCHANGED_ENTRY."""
    files = base_scope(repo, base) if base else scope(repo)
    if not only:
        return files
    return {path: files.get(path, list(UNCHANGED_ENTRY)) for path in only}


class LensOwned(list):
    """The files a reviewer owns, plus the one lens line its dispatch prompt carries."""

    def __init__(self, paths, lens):
        super().__init__(paths)
        self.lens = lens


def first_round_plan(files, structure_pass_skipped=False):
    """Which reviewers go out in the first round, and who owns which files."""
    source = [path for path in files if not source_paths.is_test_path(path)]
    tests = [path for path in files if source_paths.is_test_path(path)]
    added = sum(files[path][0] for path in files if source_paths.counts_toward_size(path))
    new_paths = [path for path in source if files[path][1] in ("??", "A")]
    large = source_paths.is_large_change(added, new_paths)

    dispatches = []
    if large and tests:
        dispatches.append(("code-reviewer", source))
        dispatches.append(("test-reviewer", tests))
    else:
        dispatches.append(("code-reviewer", list(files)))
    if large and not structure_pass_skipped:
        dispatches.append(("smell-reviewer", list(files)))
    code_owned = dispatches[0][1]
    if len(files) > 1 and len(code_owned) > 1:
        dispatches[0] = ("code-reviewer", LensOwned(code_owned, LENS_A))
        dispatches.insert(1, ("code-reviewer", LensOwned(code_owned, LENS_B)))
    return dispatches


def owns_in_round_two(agent, path, round_one_owned, test_reviewed):
    """A reviewer re-reads the files of its kind, and a test file it owned in round one that no test reviewer read."""
    if source_paths.is_test_path(path) == (agent == "test-reviewer"):
        return True
    return path in round_one_owned and path not in test_reviewed


def second_round_plan(round_fix, changed, skipped_findings, coder_diffs):
    """Which reviewers go out in round two, and who owns which files. round_fix holds (agent, owned, fixes) per
    round-one dispatch."""
    smell_runs = added_source_lines(coder_diffs) >= LARGE_ADDED_LINES
    test_reviewed = {path for agent, owned, _fixes in round_fix if agent == "test-reviewer" for path in owned}
    dispatches = []
    for agent, round_one_owned, fixes in round_fix:
        if not fixes:
            continue
        skipped_paths = [fix.path for fix in fixes if any(fix.text in item.text for item in skipped_findings)]
        owned = [path for path in dict.fromkeys(changed + skipped_paths)
                 if path and owns_in_round_two(agent, path, round_one_owned, test_reviewed)]
        if agent == "smell-reviewer" and not smell_runs:
            continue
        if not owned:
            continue
        dispatches.append((agent, owned))
    return dispatches


def added_source_lines(diffs):
    """Lines the given unified diffs add to files that count toward the size bar (`source_paths.counts_toward_size`)."""
    total, source = 0, False
    for diff in diffs:
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                source = source_paths.counts_toward_size(line[6:])
            elif line.startswith("+") and source:
                total += 1
    return total
