"""The new-side lines a work tree adds against a base: one `git diff -U0` parsed through `diff_ranges`, plus each
untracked file, which counts as added whole. Plain repo path and options; knows no review or refactor rule."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent)]
import diff_ranges
import script_utils

WHOLE_FILE = [(1, sys.maxsize)]
DIFF_ARGS = ("diff", "-U0", "--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/", "--dst-prefix=b/")


def change_added_ranges(repo, base="", detect_renames=False, literal_pathspecs=False, text_only=False):
    """{path: [(first, last)]} of the lines the work tree adds against `base` (HEAD when empty), from one `git diff`
    and one listing of the untracked files, each of which is added whole (WHOLE_FILE). With `text_only`, an untracked
    symlink, non-regular entry or file that is not UTF-8 text is left out. None when git cannot answer, as in a repo
    with no commit. Raises ValueError on a diff `diff_ranges` cannot parse."""
    git_flags = ["--literal-pathspecs"] if literal_pathspecs else []
    rename_flags = ["-M"] if detect_renames else []
    diff_text = script_utils.git_output(repo, *git_flags, *DIFF_ARGS, *rename_flags, base or "HEAD")
    untracked = script_utils.untracked_paths(repo)
    if diff_text is None or untracked is None:
        return None

    added = diff_ranges.added_ranges(diff_text)
    for untracked_path in untracked:
        if text_only and not _is_text_file(repo, untracked_path):
            continue
        added[untracked_path] = WHOLE_FILE
    return added


def _is_text_file(repo, name):
    full_path = pathlib.Path(repo) / name
    if full_path.is_symlink() or not full_path.is_file():
        return False
    return script_utils.read_text_lines(full_path) is not None
