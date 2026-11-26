"""The untracked files of a work tree, each read as numbered text lines or marked with why it is not text."""
import pathlib
from typing import NamedTuple

import script_utils

UNTRACKED_SYMLINK = "symlink"
UNTRACKED_NOT_A_FILE = "not a file"
UNTRACKED_BINARY = "binary"


class UntrackedListError(Exception):
    """git could not list the untracked files."""


class UntrackedFile(NamedTuple):
    path: str
    added_lines: list  # (line number, text) pairs; empty when kind is set
    kind: str  # why a file is not read as text: UNTRACKED_SYMLINK, UNTRACKED_NOT_A_FILE, UNTRACKED_BINARY; else ""


def untracked_files(root):
    """Untracked files git does not ignore, root-relative; a symlink, a non-regular entry or a file that cannot be
    read as UTF-8 text is listed with its kind and no lines. Raises UntrackedListError when git cannot list them."""
    names = script_utils.untracked_paths(root)
    if names is None:
        raise UntrackedListError(f"git could not list the untracked files in {root}")
    return [classify_untracked(root, name) for name in names]


def classify_untracked(root, name):
    """One untracked file, with its lines when it is a regular UTF-8 text file."""
    full_path = pathlib.Path(root) / name
    if full_path.is_symlink():
        return UntrackedFile(name, [], UNTRACKED_SYMLINK)
    if not full_path.is_file():
        return UntrackedFile(name, [], UNTRACKED_NOT_A_FILE)
    numbered = script_utils.read_text_lines(full_path)
    if numbered is None:
        return UntrackedFile(name, [], UNTRACKED_BINARY)
    return UntrackedFile(name, numbered, "")
