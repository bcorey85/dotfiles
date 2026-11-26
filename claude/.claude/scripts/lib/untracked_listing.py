"""The untracked files of a work tree, each read as numbered text lines or marked with why it is not text."""
from typing import NamedTuple

import change_added_ranges
import script_utils


class UntrackedListError(Exception):
    """git could not list the untracked files."""


class UntrackedFile(NamedTuple):
    path: str
    added_lines: list  # (line number, text) pairs; empty unless kind is UNTRACKED_TEXT
    kind: str  # why a file is not read as text (change_added_ranges.UNTRACKED_*); UNTRACKED_TEXT for text


def untracked_files(root, error_type=UntrackedListError):
    """Untracked files git does not ignore, root-relative; a symlink, a non-regular entry or a file that cannot be
    read as UTF-8 text is listed with its kind and no lines. Raises error_type when git cannot list them."""
    names = script_utils.untracked_paths(root)
    if names is None:
        raise error_type(f"git could not list the untracked files in {root}")
    return [classify_untracked(root, name) for name in names]


def classify_untracked(root, name):
    """One untracked file, with its lines when it is a regular UTF-8 text file."""
    read = change_added_ranges.read_untracked(root, name)
    return UntrackedFile(name, read.lines, read.kind)
