"""The review loop's `fix_induced` tag, set by script. A finding of round two or later is `yes` when its file:line falls
in the lines that the fix step between the previous round and this one changed, else `no`."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import diff_ranges

FIRST_TAGGED_ITER = 2


def previous_fix_ranges(out, iter_number):
    """{path: [(first, last)]} of the lines the fix after round `iter_number - 1` changed, read from the diff file
    that fix wrote under `out`; empty when the round wrote none."""
    fix_diff = pathlib.Path(out) / f"round{iter_number - 1}-fix.diff"
    if not fix_diff.is_file():
        return {}
    return diff_ranges.changed_ranges(fix_diff.read_text())


def fix_induced_tag(existing, iter_number, path, line, fix_ranges):
    """The `fix_induced` value of one finding: `existing` when the reviewer set one; "" (no tag) in round one or when
    the finding names no file:line; else `yes` when the line is inside the fix's changed lines, `no` when not."""
    if existing:
        return existing
    if iter_number < FIRST_TAGGED_ITER or not path or line <= 0:
        return ""
    inside = diff_ranges.in_ranges(fix_ranges.get(path, ()), line)
    return "yes" if inside else "no"
