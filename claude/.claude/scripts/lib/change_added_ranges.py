"""The new-side lines a work tree adds against a base: one `git diff -U0` parsed through `diff_ranges`, plus each
untracked file, which counts as added whole. Plain repo path and options; knows no review or refactor rule."""

import pathlib
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent)]
import diff_ranges
import script_utils

WHOLE_FILE = [(1, sys.maxsize)]
UNTRACKED_SYMLINK = "symlink"
UNTRACKED_NOT_A_FILE = "not a file"
UNTRACKED_BINARY = "binary"
UNTRACKED_TEXT = ""
DIFF_ARGS = ("diff", "-U0", "--no-ext-diff", "--no-textconv", "--no-color", "--src-prefix=a/", "--dst-prefix=b/")


def change_added_ranges(repo, base="", detect_renames=False, literal_pathspecs=False, text_only=False,
                        relative=False, no_renames=False):
    """{path: [(first, last)]} of the lines the work tree adds against `base` (HEAD when empty), from one `git diff`
    and one listing of the untracked files, each of which is added whole (WHOLE_FILE). With `text_only`, an untracked
    symlink, non-regular entry or file that is not UTF-8 text is left out. With `relative`, diff paths are relative
    to `repo`, as the untracked paths are. `no_renames` turns off git's own rename detection, so a renamed file
    reads as a whole added file. None when git cannot answer, as in a repo with no commit. Raises ValueError on a
    diff `diff_ranges` cannot parse."""
    git_flags = ["--literal-pathspecs"] if literal_pathspecs else []
    option_flags = ["--relative"] if relative else []
    if detect_renames:
        option_flags.append("-M")
    if no_renames:
        option_flags.append("--no-renames")
    diff_text = script_utils.git_output(repo, *git_flags, *DIFF_ARGS, *option_flags, base or "HEAD")
    untracked = script_utils.untracked_paths(repo)
    if diff_text is None or untracked is None:
        return None

    added = diff_ranges.added_ranges(diff_text)
    for untracked_path in untracked:
        if text_only and read_untracked(repo, untracked_path).kind != UNTRACKED_TEXT:
            continue
        added[untracked_path] = WHOLE_FILE
    return added


class UntrackedRead(NamedTuple):
    kind: str  # UNTRACKED_SYMLINK, UNTRACKED_NOT_A_FILE, UNTRACKED_BINARY, or UNTRACKED_TEXT
    lines: list  # (line number, text) pairs; empty unless kind is UNTRACKED_TEXT


def read_untracked(repo, name):
    """What an untracked entry is, with its numbered lines when it is a regular UTF-8 text file."""
    full_path = pathlib.Path(repo) / name
    if full_path.is_symlink():
        return UntrackedRead(UNTRACKED_SYMLINK, [])
    if not full_path.is_file():
        return UntrackedRead(UNTRACKED_NOT_A_FILE, [])
    numbered = script_utils.read_text_lines(full_path)
    if numbered is None:
        return UntrackedRead(UNTRACKED_BINARY, [])
    return UntrackedRead(UNTRACKED_TEXT, numbered)
