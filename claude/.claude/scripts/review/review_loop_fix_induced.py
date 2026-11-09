"""The review loop's `fix_induced` tag, set by script. A finding of round two or later is `yes` when its file:line falls
in the lines that the fix step between the previous round and this one changed, else `no`. The same lines bound what a
round of two or later sends to the fix coder: `split_outside_fixes`."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import diff_ranges
from review_loop_held import names_held_file

FIRST_TAGGED_ITER = 2
# The classes a fix finding outside the previous fix diff still sends to the fix coder; every other class is deferred.
FIXED_OUTSIDE_FIX_DIFF = frozenset({"bug", "correctness", "security"})


def previous_fix_diff(out, iter_number):
    """The diff file the fix after round `iter_number - 1` wrote under `out`."""
    return pathlib.Path(out) / f"round{iter_number - 1}-fix.diff"


def previous_fix_ranges(out, iter_number):
    """{path: [(first, last)]} of the lines the fix after round `iter_number - 1` changed, read from the diff file
    that fix wrote under `out`; empty when the round wrote none."""
    fix_diff = previous_fix_diff(out, iter_number)
    if not fix_diff.is_file():
        return {}
    return diff_ranges.changed_ranges(fix_diff.read_text())


def is_outside_fix(finding, iter_number, fix_ranges):
    """True when no part of `finding` is of a class in FIXED_OUTSIDE_FIX_DIFF and every part names a file:line outside
    the fix's changed lines. A part with no file:line is never outside."""
    for part in finding.each_part:
        if part.finding_class in FIXED_OUTSIDE_FIX_DIFF:
            return False
        if fix_induced_tag("", iter_number, part.path, part.line, fix_ranges) != "no":
            return False
    return True


def split_outside_fixes(out, iter_number, findings):
    """(sent, deferred): the fix findings of round `iter_number` that go to the fix coder, and those deferred to the
    hand-back because they sit outside the previous fix diff (`is_outside_fix`). Round one, and a round after a fix
    that changed no line or wrote no diff file (a run resumed with `iter:`), defer nothing."""
    if iter_number < FIRST_TAGGED_ITER:
        return list(findings), []
    fix_ranges = previous_fix_ranges(out, iter_number)
    if not fix_ranges:
        return list(findings), []

    sent, deferred = [], []
    for finding in findings:
        if is_outside_fix(finding, iter_number, fix_ranges):
            deferred.append(finding)
        else:
            sent.append(finding)
    return sent, deferred


def fix_induced_tag(existing, iter_number, path, line, fix_ranges):
    """The `fix_induced` value of one finding: `existing` when the reviewer set one; "" (no tag) in round one or when
    the finding names no file:line; else `yes` when the line is inside the fix's changed lines, `no` when not."""
    if existing:
        return existing
    if iter_number < FIRST_TAGGED_ITER or not path or line <= 0:
        return ""
    inside = diff_ranges.in_ranges(ranges_of_path(fix_ranges, path), line)
    return "yes" if inside else "no"


def ranges_of_path(fix_ranges, path):
    """The changed-line ranges of the file `path` names: its own key, or every key that `path` is a tail of (a
    reviewer may write `deep/lib.py` for `pkg/deep/lib.py`)."""
    if path in fix_ranges:
        return fix_ranges[path]
    ranges = []
    for diff_path, path_ranges in fix_ranges.items():
        if names_held_file(path, diff_path):
            ranges += path_ranges
    return ranges
