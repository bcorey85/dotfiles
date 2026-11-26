"""The simplify mode of refactor_flow: `simplify-prep` (what the complexity-reviewer is asked, the slice it gets, the
branch diff recorded before the pass) and the branch-diff comparison that `log --mode simplify` prints after it.

The branch diff is the work tree plus untracked files against the merge base of HEAD and the base. The prep
saves its per-file added and deleted lines in a sidecar beside the log input; `log` measures the same span again
and ends in STOP when added lines rose.
"""
import json
import os
from pathlib import Path
from typing import NamedTuple

import change_added_ranges
import diff_ranges
import flow_common
import numstat
import script_utils
import simplify_slices
import untracked_listing
from flow_common import (
    NoBaseError,
    NoSharedHistoryError,
    RefactorFlowError,
    diff_output,
    fresh_log_input,
    git,
    next_line,
    pick_base,
    ref_exists,
    require_repo,
    target_files,
    work_tree_merge_base,
)

MAX_SIMPLIFY_FILES = 25
SIMPLIFY_BOUND = ("Simplify mode: your bound is the whole existing code of `{target}`. Pre-existing shape IS "
                  "the target.")
SIMPLIFY_DIFF_BOUND = ("Simplify mode, diff-scoped: your bound is the added lines since `{base}` (merge base "
                       "`{merge_base}`), listed per file above. Every finding needs a site on a listed line; shape "
                       "outside those lines is not a finding, even when it causes the shape inside them. Read the "
                       "rest of a file for context only.")
SIMPLIFY_ASK = ("Find what could be deleted if this module were shaped differently: branching a data model "
                "collapses, indirection with one implementation, configurability nothing configures, guards a "
                "stronger invariant kills, values with more than one owner. Your oracle and magnitude floor are "
                "hard gates (quantified disappearance, enabling change, unreachability proof, cost clause).")
WHOLE_FILE_LABEL = "untracked, whole file"


class SpanBase(NamedTuple):
    ref: str
    source: str
    merge_base: str


class BranchStat(NamedTuple):
    merge_base: str
    files: dict  # root-relative path -> (added lines, deleted lines)


class BranchComparison(NamedTuple):
    lines: list  # what `log` prints
    stop: str  # the STOP line when added lines rose, else ""


def read_span_base(requested):
    """The base and the merge base of HEAD against it. `requested` is the --diff ref, or None for the branch-base
    helper's pick. Raises NoBaseError or NoSharedHistoryError when there is none."""
    if requested:
        if not ref_exists(requested):
            raise RefactorFlowError(f"--diff {requested} is not a commit")
        try:
            return SpanBase(requested, "--diff", work_tree_merge_base(requested))
        except NoSharedHistoryError as error:
            raise NoSharedHistoryError(
                f"STOP: {requested} and HEAD share no history; ask the user for another --diff ref.") from error
    ref, source = pick_base(None)
    return SpanBase(ref, source, work_tree_merge_base(ref))


def read_branch_stat(merge_base, root):
    """Added and deleted lines per file of the work tree against the merge base, untracked text files counted as
    all added. A binary file is left out."""
    numstat_text = diff_output(merge_base, "--numstat", "-z")
    files = numstat.changed_lines_by_path(numstat_text)
    for entry in untracked_listing.untracked_files(root, error_type=RefactorFlowError):
        if entry.kind == change_added_ranges.UNTRACKED_TEXT:
            files[entry.path] = (len(entry.added_lines), 0)
    return BranchStat(merge_base, files)


def stat_totals(stat):
    added = sum(counts[0] for counts in stat.files.values())
    deleted = sum(counts[1] for counts in stat.files.values())
    return added, deleted


def stat_summary(stat):
    added, deleted = stat_totals(stat)
    return f"{len(stat.files)} file(s) changed, {added} insertion(s)(+), {deleted} deletion(s)(-)"


def sidecar_path(input_path):
    return Path(str(input_path) + flow_common.LOG_INPUT_SIDECAR_SUFFIX)


def save_branch_stat(input_path, stat):
    content = json.dumps({"merge_base": stat.merge_base, "files": stat.files})
    script_utils.write_text_atomically(sidecar_path(input_path), content)


def load_branch_stat(input_path):
    """The stat the prep saved for this input, or None when the prep saved none. Raises RefactorFlowError on a file
    that does not hold the saved form."""
    path = sidecar_path(input_path)
    if not path.exists():
        return None
    try:
        saved = json.loads(path.read_text())
        files = {name: (int(counts[0]), int(counts[1])) for name, counts in saved["files"].items()}
        return BranchStat(str(saved["merge_base"]), files)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        raise RefactorFlowError(f"cannot read {path}: {error!r}; expected {{\"merge_base\": sha, "
                                f"\"files\": {{path: [added, deleted]}}}}; delete it to skip the comparison") from error


def grown_files(before, after):
    """(path, added lines gained) for each file whose added lines rose, in path order."""
    grown = []
    for name in sorted(after.files):
        gained = after.files[name][0] - before.files.get(name, (0, 0))[0]
        if gained > 0:
            grown.append((name, gained))
    return grown


def compare_branch_diff(input_path, root):
    """Measure the branch diff again against the prep's merge base and compare. Reads only."""
    before = load_branch_stat(input_path)
    if before is None:
        return BranchComparison(["Branch diff: no prep-time record for this input; before and after not compared."],
                                "")
    after = read_branch_stat(before.merge_base, root)
    lines = [f"Branch diff against merge base `{before.merge_base}`:",
             f"- at prep: {stat_summary(before)}",
             f"- at log:  {stat_summary(after)}"]
    added_before, _ = stat_totals(before)
    added_after, _ = stat_totals(after)
    if added_after <= added_before:
        return BranchComparison(lines, "")

    grown = ", ".join(f"{name} (+{gained})" for name, gained in grown_files(before, after))
    stop = (f"STOP: the pass raised added lines on the branch diff from {added_before} to {added_after}; files that "
            f"grew: {grown}. Tell the user, name those files, and do not report the pass as a simplification "
            f"until they rule.")
    return BranchComparison(lines, stop)


def added_line_numbers(merge_base, root):
    """{root-relative path: added line ranges text such as `3-5, 9`} of the work tree against the merge base; an
    untracked text file maps to WHOLE_FILE_LABEL."""
    try:
        ranges_by_path = change_added_ranges.change_added_ranges(root, merge_base, literal_pathspecs=True,
                                                                 text_only=True)
    except ValueError as error:
        raise RefactorFlowError(f"cannot parse the diff against {merge_base}: {error}") from error
    if ranges_by_path is None:
        raise RefactorFlowError(f"`git diff {merge_base}` failed or git could not list the untracked files")

    added = {}
    for path, ranges in ranges_by_path.items():
        if ranges == change_added_ranges.WHOLE_FILE:
            added[path] = WHOLE_FILE_LABEL
        elif ranges:
            added[path] = diff_ranges.ranges_text(ranges)
    return added


def scope_to_added(found, added, prefix):
    """{file: its added-lines text} for the files (relative to the cwd; `prefix` is the cwd's path below the repo
    root) that hold an added line."""
    scoped = {}
    for name in found:
        text = added.get(os.path.normpath(prefix + name))
        if text:
            scoped[name] = text
    return scoped


def print_complexity_prompt(chosen, bound, ranges):
    print("## complexity-reviewer dispatch prompt (pinned; omit `model`; never +fast)")
    print("Files:")
    for name in chosen:
        suffix = f" (added lines: {ranges[name]})" if ranges else ""
        print(f"- {name}{suffix}")
    print(bound)
    print(SIMPLIFY_ASK)
    print("Add any project constraint you know that makes a shape mandatory (a required layer, a framework "
          "seam, a public contract).")


def base_note_for(err):
    """Why the prompt runs with no recorded branch diff."""
    if isinstance(err, NoBaseError):
        return "no base found"
    if isinstance(err, NoSharedHistoryError):
        return "the base shares no history with HEAD"
    return f"the base could not be read: {err}"


def simplify_prep(opts):
    root = require_repo()
    span_base, base_note = None, ""
    try:
        span_base = read_span_base(opts.diff)
    except RefactorFlowError as err:
        if opts.diff:
            if isinstance(err, (NoBaseError, NoSharedHistoryError)):
                print(err)
                return 0
            raise
        base_note = base_note_for(err)

    added = None
    prefix = ""
    if opts.diff:
        added = added_line_numbers(span_base.merge_base, root)
        prefix = git("rev-parse", "--show-prefix").stdout.strip()

    files_by_target = []
    ranges = {}
    for target in opts.target:
        found = target_files([target])
        if not found:
            print(f"STOP: `{target}` holds no tracked or untracked (not ignored) file; "
                  "ask the user for a dir or module.")
            return 0
        if added is not None:
            scoped = scope_to_added(found, added, prefix)
            if not scoped:
                print(f"STOP: `{target}` holds no file with a line added since `{opts.diff}`; "
                      "ask the user for a dir or module.")
                return 0
            ranges.update(scoped)
            found = list(scoped)
        files_by_target.append((target, found))
    return simplify_report(opts, files_by_target, root, span_base, base_note, ranges)


def simplify_report(opts, files_by_target, root, span_base, base_note, ranges):
    label = " ".join(target for target, _files in files_by_target)
    try:
        plan = simplify_slices.plan_slices(files_by_target, MAX_SIMPLIFY_FILES)
    except simplify_slices.SliceError as error:
        raise RefactorFlowError(f"simplify-prep: {error}") from error
    dropped_text = simplify_slices.dropped_summary(plan.dropped)
    slices = plan.slices
    if not slices:
        print(f"STOP: `{label}` holds only test, index, style or generated files ({dropped_text} "
              f"dropped); ask the user for a source dir or module.")
        return 0
    if not 1 <= opts.slice <= len(slices):
        raise RefactorFlowError(f"--slice {opts.slice} out of range 1..{len(slices)}")
    chosen = slices[opts.slice - 1]
    log_input = fresh_log_input()

    print(f"## Simplify target `{label}` ({plan.kept} source file(s))")
    print(f"Dropped as not source: {dropped_text} file(s).")
    if len(slices) > 1:
        print(f"Over {MAX_SIMPLIFY_FILES} files: split into {len(slices)} slices along module folders. This run "
              f"is slice {opts.slice} of {len(slices)} ({len(chosen.files)} files); modules: "
              f"{', '.join(chosen.modules)}; tell the user which slice runs, "
              f"re-run with `--slice N` for the others.")
    print_branch_stat_record(log_input, span_base, base_note, root)
    print()
    bound = SIMPLIFY_BOUND.format(target=label)
    if ranges:
        bound = SIMPLIFY_DIFF_BOUND.format(base=span_base.ref, merge_base=span_base.merge_base)
    print_complexity_prompt(chosen.files, bound, ranges)
    print()
    print(next_line("do NOT read the files; dispatch ONE complexity-reviewer with the prompt above; triage "
                    "(drop oracle-failures, under-floor, irreducible; `[design-decision]` to the user); present "
                    "survivors; on chosen fixes follow step 5 with the test audit mandatory; then "
                    f"write the log input to {log_input} and call `log --mode simplify --input {log_input}` "
                    "with `target` = the files listed in the prompt. Every finder finding "
                    "goes in `findings`: survivors the user declined get actioned=none, triage drops get "
                    "actioned=skipped_fp. Log empty-handed only when the finder returned nothing."))
    return 0


def print_branch_stat_record(log_input, span_base, base_note, root):
    """Save the branch diff as it stands before the pass, and print it."""
    if span_base is None:
        print(f"Branch diff: not recorded ({base_note}); `log` will not compare before and after.")
        return
    stat = read_branch_stat(span_base.merge_base, root)
    save_branch_stat(log_input, stat)
    print(f"Branch diff at prep, against merge base `{span_base.merge_base}` (base `{span_base.ref}` from "
          f"{span_base.source}): {stat_summary(stat)}")
